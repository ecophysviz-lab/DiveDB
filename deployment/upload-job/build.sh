SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: $SCRIPT_DIR"

kubectl delete jobs divedb-uploader-job
kubectl apply -f $SCRIPT_DIR/job.yaml