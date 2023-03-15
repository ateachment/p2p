# Install K8s Controller script for Debian 11
# https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/

# Update the apt package index and install packages needed to use the Kubernetes apt repository
apt-get update
apt-get install -y ca-certificates curl

# In releases older than Debian 12 and Ubuntu 22.04, /etc/apt/keyrings does not exist by default.
$KEYRINGS_DIR = "/etc/apt/keyrings"

if [ ! -d "$KEYRINGS_DIR" ]; then
  echo "$KEYRINGS_DIR does not yet exist. Will be created."
  mkdir $KEYRINGS_DIR
  chmod 755 $KEYRINGS_DIR
fi

# Download the Google Cloud public signing key:
curl -fsSLo /etc/apt/keyrings/kubernetes-archive-keyring.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg

# Add the Kubernetes apt repository:
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | tee /etc/apt/sources.list.d/kubernetes.list

# Update apt package index with the new repository and install 
# kubectl: the command line util to talk to your cluster 
# kubeadm: the command to bootstrap the cluster.
# kubelet: the component that runs on all of the machines in your cluster and does things like starting pods and containers.
apt-get update
apt-get install -y kubelet kubeadm kubectl

# pin their version
apt-mark hold kubelet kubeadm kubectl


# Enable kubectl autocompletion
echo 'source <(kubectl completion bash)' >>~/.bashrc

