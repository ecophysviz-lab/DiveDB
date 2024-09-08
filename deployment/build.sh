
# Use docker compose to build the required images
# make build

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: $SCRIPT_DIR"


kubectl apply -f $SCRIPT_DIR/pg.pvc.yaml
kubectl apply -f $SCRIPT_DIR/pg.deployment.yaml
kubectl apply -f $SCRIPT_DIR/pg.service.yaml
kubectl apply -f $SCRIPT_DIR/pg.ingress.yaml

