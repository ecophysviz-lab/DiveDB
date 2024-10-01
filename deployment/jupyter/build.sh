source .env

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: $SCRIPT_DIR"

kubectl delete -f $SCRIPT_DIR/jupyter.deployment.yaml
kubectl apply -f $SCRIPT_DIR/jupyter.deployment.yaml
kubectl apply -f $SCRIPT_DIR/jupyter.service.yaml
kubectl apply -f $SCRIPT_DIR/jupyter.ingress.yaml



# kubectl apply -f $SCRIPT_DIR/django/django.deployment.yaml