sudo python -m ensurepip --default-pip
sudo amazon-linux-extras install -y ansible2
pip install -r ansible/requirements.txt --user

if [ ! -d ~/.ansible/collections/ansible_collections/community/aws ] ; then
  ansible-galaxy collection install community.aws
fi

echo cd ansibile 
echo ansible-playbook -i inventories/spp/dev --vault-password-file vault_password create.yml
