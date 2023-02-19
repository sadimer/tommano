# TOMMANO - TOSCA multi-cloud orchestration framework for NFV MANO
![logo](tommano.jpg?raw=true "logo")
# Installation:
1. Install this application:
```
git clone https://github.com/sadimer/tommano
cd tommano
pip install -r requirements.txt
python setup.py install
cd ..
```
2. Install clouni (or any other tosca orchestrator):
```
git clone https://github.com/ispras/clouni
cd clouni
pip install -r requirements.txt
python setup.py install
cd ..
cd tommano
```
3. Install sshpass:
```
sudo apt install sshpass
```

# Using:
1. To begin with, you need a topology template in the NFV MANO notation, the examples are in the examples folder. You can check it for correctness:
```
tommano --template-file examples/demo_nfv_example.yaml --validate-only
```
2. Generate a normative topology template:
```
tommano --template-file examples/demo_nfv_example.yaml --output-dir results --orchestrator=clouni
```
3. Next, the topology.yaml file will appear in the specified folder, it must be passed to the tosca input to the orchestrator:
```
cd results
clouni --template-file ./topology.yaml --cluster-name example --provider openstack --configuration-tool ansible --output-file ./ansible_create.yaml --extra ignore_errors=true --host-parameter private_address
```
4. Deploying a topology template in the cloud based on openstack using ansible:
```
sudo ansible-playbook ansible_create.yaml --extra-vars ansible_sudo_pass=admincumulus --extra-vars ansible_user=cumulus
```
We get an example of a network infrastructure (with NAT, DPI, Firewall, DHCP, DNS, configured routing and traffic analysis):
![model](tosca-nfv.png?raw=true "model")
