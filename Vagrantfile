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
      machine.vm.box = "chef/fedora-20-i386"
      #machine.vm.hostname = name
      machine.vm.network "private_network", ip: ip
      machine.vm.provision "shell",
        inline: "echo '123456'| passwd root --stdin"
      machine.vm.provider "virtualbox" do |v|
          v.name = name
          v.customize ["modifyvm", :id, "--memory", 200]
          if name.include? "2" or name.include? "3"
            (1..3).each do |i|
              # I'm manually transforming i into binary (port, device), because
              # I don't know ruby and I'm lazy
              port = 1
              if i == 1 then port = 0 end
              device = i % 2
              disk = disk_file_path + name + i.to_s() + ".vdi"
              v.customize ['createhd', '--filename', disk, '--size', 1024]
              v.customize ['storageattach', :id,
                           '--storagectl', 'IDE Controller',
                           '--port', port, '--device', device , '--type', 'hdd',
                           '--medium', disk]
            end
          end
      end
    end
  end
end
