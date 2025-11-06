"""
Notion ORM - A lightweight ORM-like interface for querying Notion databases.

This module provides an easy way to define models that map to Notion databases
and query them using a familiar ORM-like syntax.
"""

import datetime
from typing import Dict, List, Any, Optional, ClassVar, Type

from notion_client import Client


class ModelObjects:
    """
    Query manager for NotionModel.
    """

    def __init__(self, model_cls):
        self.model_cls = model_cls
        self._filters = []

    def all(self) -> List:
        """Get all records from the database."""
        return self._query()

    def filter(self, **kwargs) -> "ModelObjects":
        """
        Filter records based on provided criteria.

        Args:
            **kwargs: Filter criteria
            For properties with spaces, use underscores in the keyword argument:
            e.g., Project_ID="123" for "Project ID" property

        Returns:
            Self for method chaining
        """
        self._filters = self._build_filters(kwargs)
        return self

    def first(self) -> Optional["NotionModel"]:
        """Get the first result."""
        results = self._query(limit=1)
        return results[0] if results else None

    def _build_filters(self, kwargs: Dict) -> List[Dict]:
        """
        Build Notion API filter objects from kwargs.

        Handles property names with spaces by converting underscores to spaces
        when looking up in the schema.
        """
        filters = []
        schema = self.model_cls._meta.schema

        for key, value in kwargs.items():
            # Convert underscores to spaces for schema lookup
            schema_key = key.replace("_", " ")

            # Try exact match first, then try with converted spaces
            prop_info = schema.get(schema_key)
            if not prop_info:
                # Try the original key as fallback
                prop_info = schema.get(key)
                if not prop_info:
                    raise ValueError(
                        f"Property '{key}' (or '{schema_key}') not found in schema"
                    )
                schema_key = key  # Use original key if that's what matched

            prop_type = prop_info.get("type")

            if prop_type == "title":
                filters.append({"property": schema_key, "title": {"equals": value}})
            elif prop_type == "rich_text":
                filters.append({"property": schema_key, "rich_text": {"equals": value}})
            elif prop_type == "number":
                filters.append({"property": schema_key, "number": {"equals": value}})
            elif prop_type == "select":
                filters.append({"property": schema_key, "select": {"equals": value}})
            elif prop_type == "multi_select":
                filters.append(
                    {"property": schema_key, "multi_select": {"contains": value}}
                )
            elif prop_type == "date":
                if isinstance(value, (datetime.date, datetime.datetime)):
                    value = value.isoformat()
                filters.append({"property": schema_key, "date": {"equals": value}})
            elif prop_type == "relation":
                # Handle relation filtering by ID
                filters.append(
                    {"property": schema_key, "relation": {"contains": value}}
                )
            elif prop_type == "checkbox":
                filters.append({"property": schema_key, "checkbox": {"equals": value}})
            elif prop_type == "formula":
                # Formula filtering depends on the formula result type
                formula_type = prop_info.get("formula", {}).get("type")
                if formula_type == "string":
                    filters.append(
                        {
                            "property": schema_key,
                            "formula": {"string": {"equals": value}},
                        }
                    )
                elif formula_type == "number":
                    filters.append(
                        {
                            "property": schema_key,
                            "formula": {"number": {"equals": value}},
                        }
                    )
                elif formula_type == "boolean":
                    filters.append(
                        {
                            "property": schema_key,
                            "formula": {"boolean": {"equals": value}},
                        }
                    )
                elif formula_type == "date":
                    if isinstance(value, (datetime.date, datetime.datetime)):
                        value = value.isoformat()
                    filters.append(
                        {"property": schema_key, "formula": {"date": {"equals": value}}}
                    )

        return filters

    def _query(self, limit=None) -> List["NotionModel"]:
        """
        Execute the query against Notion API.

        Returns:
            List of model instances
        """
        client = self.model_cls._meta.notion_client
        db_id = self.model_cls._meta.database_id

        query_args = {}
        if self._filters:
            query_args["filter"] = {"and": self._filters}

        if limit:
            query_args["page_size"] = limit

        results = []
        has_more = True
        start_cursor = None

        while has_more:
            if start_cursor:
                query_args["start_cursor"] = start_cursor

            response = client.databases.query(database_id=db_id, **query_args)

            for page in response.get("results", []):
                results.append(self.model_cls._from_notion_page(page))

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

            if limit and len(results) >= limit:
                break

        return results


class NotionModel:
    """
    Base class for Notion database models.
    """

    objects: ClassVar[ModelObjects]
    _meta: ClassVar[Any]

    def __init__(self, **kwargs):
        """
        Initialize a model instance.

        Args:
            **kwargs: Model field values
        """
        self._raw_data = {}
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __init_subclass__(cls, **kwargs):
        """
        Set up class when a subclass is created.
        """
        super().__init_subclass__(**kwargs)
        cls.objects = ModelObjects(cls)

    @classmethod
    def _from_notion_page(cls, page_data: Dict) -> "NotionModel":
        """
        Create a model instance from Notion page data.

        Args:
            page_data: Raw Notion page data

        Returns:
            Model instance
        """
        instance = cls()
        instance._raw_data = page_data
        instance.id = page_data.get("id")
        instance.url = page_data.get("url")
        instance.created_time = page_data.get("created_time")
        instance.last_edited_time = page_data.get("last_edited_time")

        # Extract page icon (root-level property)
        icon_data = page_data.get("icon")
        if icon_data:
            icon_type = icon_data.get("type")
            if icon_type == "emoji":
                instance.icon = icon_data.get("emoji")
            elif icon_type == "file":
                instance.icon = icon_data.get("file", {}).get("url")
            elif icon_type == "external":
                instance.icon = icon_data.get("external", {}).get("url")
            else:
                instance.icon = None
        else:
            instance.icon = None

        # Parse properties
        properties = page_data.get("properties", {})
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get("type")

            if prop_type == "title":
                value = cls._parse_title(prop_data.get("title", []))
            elif prop_type == "rich_text":
                value = cls._parse_rich_text(prop_data.get("rich_text", []))
            elif prop_type == "number":
                value = prop_data.get("number")
            elif prop_type == "select":
                value = cls._parse_select(prop_data.get("select"))
            elif prop_type == "multi_select":
                value = cls._parse_multi_select(prop_data.get("multi_select", []))
            elif prop_type == "date":
                value = cls._parse_date(prop_data.get("date"))
            elif prop_type == "relation":
                # Store relation IDs for lazy loading
                value = prop_data.get("relation", [])
            elif prop_type == "checkbox":
                value = prop_data.get("checkbox")
            elif prop_type == "url":
                value = prop_data.get("url")
            elif prop_type == "email":
                value = prop_data.get("email")
            elif prop_type == "phone_number":
                value = prop_data.get("phone_number")
            elif prop_type == "formula":
                formula_type = prop_data.get("formula", {}).get("type")
                if formula_type:
                    value = prop_data.get("formula", {}).get(formula_type)
                else:
                    value = None
            else:
                value = None

            setattr(instance, prop_name, value)

        return instance

    @staticmethod
    def _parse_title(title_blocks):
        """Parse title property to string."""
        if not title_blocks:
            return ""
        return "".join(block.get("plain_text", "") for block in title_blocks)

    @staticmethod
    def _parse_rich_text(text_blocks):
        """Parse rich text property to string."""
        if not text_blocks:
            return ""
        return "".join(block.get("plain_text", "") for block in text_blocks)

    @staticmethod
    def _parse_select(select_data):
        """Parse select property."""
        if not select_data:
            return None
        return select_data.get("name")

    @staticmethod
    def _parse_multi_select(multi_select_data):
        """Parse multi-select property to list of strings."""
        if not multi_select_data:
            return []
        return [item.get("name") for item in multi_select_data]

    @staticmethod
    def _parse_date(date_data):
        """Parse date property to datetime."""
        if not date_data:
            return None

        start_date = date_data.get("start")
        if not start_date:
            return None

        # Handle both date-only and datetime formats
        if "T" in start_date:
            return datetime.datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        else:
            return datetime.date.fromisoformat(start_date)


class NotionORMManager:
    """
    Manager class for handling Notion database models and queries.
    """

    # TODO: IDENTIFY ORPHAN DATALAKES

    def __init__(self, db_map: Dict[str, str], token: str):
        """
        Initialize the NotionORMManager.

        Args:
            db_map: Dictionary mapping database names to their Notion database IDs
            token: Notion API token
        """
        self.db_map = db_map
        self.client = Client(auth=token)
        self._models = {}
        self._schemas = {}

    def _initialize_schema(self, db_name: str) -> Dict:
        """
        Fetch and cache the schema for a database.
        """
        db_id = self.db_map.get(db_name)
        if not db_id:
            raise ValueError(f"Database '{db_name}' not found in database map")

        db_info = self.client.databases.retrieve(database_id=db_id)
        self._schemas[db_name] = db_info.get("properties", {})
        return self._schemas[db_name]

    def get_model(self, model_name: str) -> Type[NotionModel]:
        """
        Get or create a model class for a Notion database.

        Args:
            model_name: Name of the model/database

        Returns:
            Model class for the specified database
        """
        if model_name in self._models:
            return self._models[model_name]

        # Create new model
        db_name = f"{model_name} DB" if not model_name.endswith(" DB") else model_name
        db_name = db_name.replace("s DB", " DB")
        db_id = self.db_map.get(db_name)

        if not db_id:
            raise ValueError(f"Database '{db_name}' not found in database map")

        # Get database schema
        schema = self._initialize_schema(db_name)

        # Create model class
        model = type(model_name, (NotionModel,), {})

        # Set meta attributes directly on the class
        model._meta = type(
            "Meta",
            (),
            {
                "database_id": db_id,
                "database_name": db_name,
                "notion_client": self.client,
                "schema": schema,
                "manager": self,
            },
        )()

        self._models[model_name] = model

        # Inject query methods based on schema
        self._inject_query_methods(model)

        # Inject relationship methods
        self._inject_relationship_methods(model, schema)

        return model

    def _inject_query_methods(self, model: Type[NotionModel]):
        """
        Inject query methods based on the schema.
        """

        def get_by_query(cls, query):
            query_dict = {}
            for key, value in query.items():
                query_dict[key] = value
            return cls.objects.filter(**query_dict).first()

        # Add a get_{model_name} method to the model class
        setattr(model, f"get_{model.__name__.lower()}", classmethod(get_by_query))

    def _inject_relationship_methods(self, model: Type[NotionModel], schema: Dict):
        """
        Inject relationship methods based on the schema.
        """
        for prop_name, prop_data in schema.items():
            prop_type = prop_data.get("type")

            if prop_type == "relation":
                # Get the related database ID
                relation_db_id = prop_data.get("relation", {}).get("database_id")

                if not relation_db_id:
                    continue

                # Normalize the relation ID by removing dashes for comparison
                normalized_relation_id = relation_db_id.replace("-", "")

                # Reverse-lookup the actual database name from the relation ID
                target_db_name = None
                for db_name, db_id in self.db_map.items():
                    # Normalize the database ID by removing dashes for comparison
                    normalized_db_id = db_id.replace("-", "")
                    if normalized_db_id == normalized_relation_id:
                        target_db_name = db_name
                        break

                # Determine the related model name from the actual target database
                if target_db_name:
                    # Use the actual target database name (e.g., "Signal DB")
                    related_model_name = target_db_name
                else:
                    # Fallback to the property name for backward compatibility
                    related_model_name = f"{prop_name} DB"

                if related_model_name:
                    # Create method name based on the target database, not the property name
                    # (e.g., "Signal DB" -> "get_signal")
                    method_name = f"get_{related_model_name.replace(' DB', '').replace(' ', '_').lower()}"

                    # Define method
                    def get_related(
                        self, prop_name=prop_name, related_model_name=related_model_name
                    ):
                        related_ids = (
                            self._raw_data.get("properties", {})
                            .get(prop_name, {})
                            .get("relation", [])
                        )
                        if not related_ids:
                            return []

                        related_model = self._meta.manager.get_model(related_model_name)
                        results = []

                        for rel_id in related_ids:
                            page_id = rel_id.get("id")
                            if page_id:
                                page_data = self._meta.notion_client.pages.retrieve(
                                    page_id=page_id
                                )
                                results.append(
                                    related_model._from_notion_page(page_data)
                                )

                        return results

                    # Add method to model
                    setattr(model, method_name, get_related)
