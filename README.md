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

Open shown URL with the browser, i.e. http://127.0.0.1:5000 

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


## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)
