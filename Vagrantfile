# -*- mode: ruby -*-
# vi: set ft=ruby:shiftwidth=2: tabstop=2: softtabstop=2 :

hosts = {
  "destroystack1" => "192.168.33.11",
  "destroystack2" => "192.168.33.22",
  "destroystack3" => "192.168.33.33",
}

disk_file_path = './tmp/'

VAGRANTFILE_API_VERSION = "2"


Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.ssh.forward_agent = true

  hosts.each do |name, ip|
    config.vm.define name do |machine|
      machine.vm.box = "fedora-18"
      #machine.vm.box_url = "http://static.stasiak.at/fedora-18-x86-2.box"
      #machine.vm.hostname = name
      machine.vm.network "private_network", ip: ip
      machine.vm.provision "shell",
        inline: "echo '123456'| passwd root --stdin"
      machine.vm.provider "virtualbox" do |v|
          v.name = name
          v.customize ["modifyvm", :id, "--memory", 200]
          if name.include? "2" or name.include? "4"
            (1..3).each do |i|
              disk = disk_file_path + name + i.to_s() + ".vdi"
              v.customize ['createhd', '--filename', disk, '--size', 1024]
              v.customize ['storageattach', :id, '--storagectl', 'SATA',
                           '--port', i, '--device', 0, '--type', 'hdd',
                           '--medium', disk]
            end
          end
      end
    end
  end
end
