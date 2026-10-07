# Peer To Peer - P2P

<p>Development of a Peer-to-Peer web application with Flask for teaching purposes.</p>

Includes until now:

<ul>
<li>Web service that provides its own IP address</li>
<li>pytest file</li>
</ul>

## Installation

Clone the repository:

```bash
git clone https://github.com/ateachment/p2p.git
cd p2p
```

Create a Python virtual environment:

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
python3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the required Python packages:

```bash
python -m pip install -r requirements.txt
```

## Program start

Start the Flask application:

```bash
python publish_some_peer_ips.py
```

Open the shown URL with a browser, e.g.:

<http://127.0.0.1:5000>

or use the terminal:

```bash
curl http://127.0.0.1:5000
```

## Testing

Run the tests with:

```bash
python -m pytest
```

or run the specific test file:

```bash
python -m pytest test_publish_some_peer_ips.py
```

## Docker

Build the Docker image based on *Alpine Linux*:

```bash
docker build -t p2p/main .
```

Run the Docker container:

```bash
docker run -it -p 8888:5000 p2p/main
```

The application can then be accessed through the Docker host:

<http://127.0.0.1:8888>

The container can also be started in detached mode:

```bash
docker run -d -p 8888:5000 p2p/main
```

To get the IP address of the Docker host, use:

```bash
ip address
```

The application can then be accessed through the host's IP address and port 8888, e.g.:

<http://192.168.178.13:8888>

## Docker Compose

Run Docker Compose with the previously built image:

```bash
docker compose up
```

The two peers can then be accessed through the Docker host using ports 5000 and 5001, e.g.:

<http://192.168.178.13:5000>

and

<http://192.168.178.13:5001>

## Kubernetes

Run `services/p2p.yaml` to deploy the P2P application in Kubernetes.

The Kubernetes configuration uses container images from GitHub Container Registry (`ghcr.io`). The images are created by the GitHub Actions CI/CD pipeline.

```bash
kubectl apply -f https://raw.githubusercontent.com/ateachment/p2p/main/services/p2p.yaml
```

Get the IP addresses of the pods:

```bash
kubectl describe service p2p-service -n p2p-namespace
```

Call the application with:

```bash
curl http://<pod-ip>:5000
```

Alternatively, get the names of the pods:

```bash
kubectl get pods -n p2p-namespace
```

The application can then be called from inside a pod:

```bash
kubectl exec -it <name-of-pod> -n p2p-namespace -- curl http://localhost:5000
```

A shell can also be opened inside a pod:

```bash
kubectl exec -it <name-of-pod> -n p2p-namespace -- sh
```

The application can then be called from inside the pod:

```bash
curl http://<name-of-pod>.p2p-service:5000
```

Stop the P2P application with:

```bash
kubectl delete StatefulSet p2p-statefulset -n p2p-namespace
kubectl delete service p2p-service -n p2p-namespace
```

Alternatively, the complete namespace can be deleted:

```bash
kubectl delete namespace p2p-namespace
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)