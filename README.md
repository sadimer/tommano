# nfv_tosca_translator

В современных реалиях технология NFV набирает все большую популярность. Она позволяет заменить физические сетевые устройства программными модулями, работающими на серверах или виртуальных машинах. Это позволяет избавиться от большого количества проприетарного сетевого оборудования, которое сложно настраивать, дорого содержать и очень трудно обновлять.
Однако развёртывание и сопровождение функций этого оборудования (firewall, NAT, спам-фильтр, ограничение скорости доступа) в виде программного компонента (VNF), настройка конфигураций этих компонентов, ручная настройка маршрутизации трафика — все еще трудозатратные операции (особенно для больших и сложных сетевых инфраструктур).

В данной работе мною предложено решение данной проблемы за счет создания приложения, способного декларативно представить описание сетевой инфраструктуры в нотации NFV в виде нормативного TOSCA шаблона, который впоследствии может быть использован для развертывания соответствующей сетевой инфраструктуры в облаке с помощью tosca оркестратора.

# Установка:
1. Установите tosca-parser:
```
git clone https://github.com/bura2017/tosca-parser.git
cd tosca-parser
git checkout develop
pip install -r requirements.txt
python setup.py install
cd ..
```
2. Установите данное приложение:
```
git clone https://github.com/sadimer/nfv_tosca_translator
cd nfv_tosca_translator
pip install -r requirements.txt
python setup.py install
cd ..
```
3. Установите clouni (или любой другой tosca оркестратор):
```
git clone https://github.com/ispras/clouni
cd clouni
pip install -r requirements.txt
python setup.py install
cd ..
cd nfv_tosca_translator
```

# Использование:
1. Для начала необходим шаблон топологии в нотации nfv, примеры находятся в папке examples. Можете проверить его на корректность:
```
nfv_tosca_translator --template-file examples/demo_nfv_example.yaml --validate-only
```
2. Сгенерируйте нормативный шаблон топологии:
```
nfv_tosca_translator --template-file examples/demo_nfv_example.yaml --output-dir results --orchestrator=clouni
```
3. Далее в указанной папке появится файл topology.yaml, его необходимо передать на вход tosca оркестратору:
```
cd results
clouni --template-file topology.yaml --cluster-name example --provider openstack --configuration-tool ansible --output-file ansible_create.yaml --extra ignore_errors=true
```
4. Разворачиваем шаблон топологии в облаке на базе openstack при помощи ansible:
```
ansible-playbook ansible_create.yaml --become-user root
```
Получаем развернутый пример сетевой инфраструктуры (c NAT, nDPI, Firewall, DHCP, DNS, настроенной маршрутизацией и анализом трафика):
![model](tosca-nfv.png?raw=true "model")
