# Peer To Peer - P2P
<p>Development of a Peer to peer web application with Flask for teaching purposes.</p>

Includes until now:
<ul>
<li>Web service that provides the own ip address</li>
<li>pytest file</li>
</ul>

## Installation

Clone repository
```bash
git clone https://github.com/ateachment/p2p.git
```

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install requirements.

```bash
pip install -r requirements.txt
```

## Program start

```bash
cd p2p
python publishSomePeerIPs.py
```

Open shown URL with the browser, i.e. http://127.0.0.1:5000 <br>
or in terminal
```bash
curl -X 'GET' 'http://192.168.178.113:8888'
```

## Testing

Start the test program with 
```bash
pytest testPublishSomePeerIPs.py
```

## Docker

Build docker image based on <i>alpine</i>
```bash
docker build p2p -t p2p/main
```
Run docker image 
```bash
docker run -it -p 8888:5000 p2p/main
```
or in detached mode (no ip address is shown)
```bash
docker run -itd -p 8888:5000 p2p/main
```
Open local or docker URLs with browser<br>
http://127.0.0.1:5000 or i.e. http://172.17.0.2:5000
or
get ip adress of docker host
```bash
ip address
```
and open host URL with browser<br>
i.e. http://192.168.178.13:8888

## Docker Compose

Run docker compose with previous build image 
```bash
cd p2p
docker-compose up
```
Open host URLs with browser with ports 5000 for peer1 and 5001 for peer2<br>
i.e. http://192.168.178.13:5000 and http://192.168.178.13:5001

## Kubernetes

Run /services/p2p.yaml to deploy images from Github's Docker Container Registry ghcr.io<br>
which was created by .github\workflows/actions.yml (CI/CD pipeline)
```bash
kubectl apply -f https://raw.githubusercontent.com/ateachment/p2p/main/services/p2p.yaml
```

Get IP addresses of pods
```bash
kubectl describe service p2p-service -n p2p-namespace
```

Call app with
```bash
curl http://<pod-ip>:5000
```

Stop pods with
```bash
kubectl delete deployment p2p-deployment -n p2p-namespace && kubectl delete service p2p-service -n p2p-namespace 
```
or
```bash
kubectl delete namespace p2p-namespace
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)
