#!/usr/bin/env python
# −*− coding: UTF−8 −*−
import zerorpc
import os
import socket
import shutil
import string
import uuid
import xmlrpclib
import pickle
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s (%(lineno)d) - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class AgentApi(object):
    """ This is the Agent Api
    """
    def __init__(self, base_path="/opt/metrops/instances"):
        self.max_slots = 10
        self.base_path = base_path
        self.used_slots = self._get_used_slots()
        self.port_range = range(11500, 11700)
        self.free_ports = self._get_free_ports()

    def get_slots(self):
        return {'slots': {
                            'max': self.max_slots, 
                            'free': self.max_slots - self.used_slots, 
                            'instances': self.get_instances()
                        }
                }

    def _get_free_ports(self):
        instances = [ name for name in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, name)) ]
        used_ports = {}
        port_range = self.port_range
        for instance in instances:
            with open(os.path.join(self.base_path, instance, 'metrops.data'), 'r') as f:
                used_ports = pickle.load(f)
                logger.debug("instance: %s, ports: %s" % (instance, used_ports))
        for port in used_ports.values():
            if port in port_range:
                port_range.remove(port)
        return port_range


    def get_instances(self):
        return [ name for name in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, name)) ]

    def _get_used_slots(self):
        instances = self.get_instances()
        return len(instances)

    def _make_instance_directory_tree(self, instance):
        if not os.path.exists(os.path.join(self.base_path, instance)):
            instance_path = os.path.join(self.base_path, instance)
            # Create base instance directory
            os.makedirs(instance_path)
            # Create base layout
            for name in ['log', 'storage', 'carbon', 'graphite', 'riemann', 'collectd']:
                os.makedirs(os.path.join(instance_path, name))
            os.makedirs(os.path.join(instance_path, 'storage', 'whisper'))
            os.makedirs(os.path.join(instance_path, 'storage', 'lists'))
            os.makedirs(os.path.join(instance_path, 'storage', 'rrd'))
            os.makedirs(os.path.join(instance_path, 'storage', 'graphite_rrd'))

    def _get_free_port(self, num=1):
        ports = []
        for port in range(num):
            ports.append(self.free_ports[-1])
            self.free_ports.pop()
        return ports

    def create_instance(self, instance, password):
        if self.used_slots >= self.max_slots:
            return {'error': {'message': "Max slots reached"}}
        if not os.path.exists(os.path.join(self.base_path, instance)):
            self._make_instance_directory_tree(instance)
            # reserve ports
            port, carbon_port, carbon_pickle_port, carbon_cache_query_port, graphite_port = self._get_free_port(num=5)
            # pickle data to file
            ports = {'carbon_port': carbon_port,
                    'carbon_pickle_port': carbon_pickle_port,
                    'carbon_cache_query_port': carbon_cache_query_port,
                    'graphite_port': graphite_port,
                    'port': port
                    }
            with open(os.path.join(self.base_path, instance, 'metrops.data'), 'w+') as f:
                pickle.dump(ports, f)
            # Write authfile
            with open(os.path.join(self.base_path, instance, 'collectd', 'authfile'), 'w+') as f:
                f.write("%s:%s" % (instance,password))
            # Write collectd template
            with open(os.path.join('/opt/metrops', 'templates', 'collectd.conf'), 'r') as f:
                collectd_conf = f.read()
            collectd_conf = collectd_conf.format(
                                                ip_address = '127.0.0.1',
                                                collectd_port = port,
                                                carbon_port = carbon_port,
                                                instance = instance,
                                                )
            with open(os.path.join(self.base_path, instance, 'collectd', 'collectd.conf'), 'w+') as f:
                f.write(collectd_conf)
            # Write custom types.db
            with open(os.path.join('/opt/metrops', 'templates', 'my_types.db'), 'r') as f:
                my_types_db = f.read()
            with open(os.path.join(self.base_path, instance, 'collectd', 'my_types.db'), 'w+') as f:
                f.write(my_types_db)
            # add instance to supervisor and start collectd
            s = xmlrpclib.ServerProxy('http://metrops:metrops@localhost:9001')
            s.twiddler.addProgramToGroup('instances', 'collectd-%s' % instance, 
                    {'command':'/opt/metrops/collectd/sbin/collectd -f -C /opt/metrops/instances/%s/collectd/collectd.conf' % instance, 
                        'autostart':'true', 
                        'autorestart':'true', 
                        'startsecs':'0',
                        'stdout_logfile':'/opt/metrops/instances/%s/log/collectd-stdout.log' % instance,
                        'stdout_logfile_maxbytes':'1MB',
                        'stdout_logfile_backups':10,
                        'stdout_capture_maxbytes':'1MB',
                        'stderr_logfile':'/opt/metrops/instances/%s/log/collectd-stderr.log' % instance,
                        'stderr_logfile_maxbytes':'1MB',
                        'stderr_logfile_backups':10,
                        'stderr_capture_maxbytes':'1MB'
                    }
                )
            # Write carbon template
            with open(os.path.join('/opt/metrops', 'templates', 'carbon.conf'), 'r') as f:
                carbon_conf = f.read()
            carbon_conf = carbon_conf.format(
                        carbon_port = carbon_port,
                        carbon_pickle_port = carbon_pickle_port,
                        carbon_cache_query_port = carbon_cache_query_port,
                        instance = instance
                    )
            with open(os.path.join(self.base_path, instance, 'carbon', 'carbon.conf'), 'w+') as f:
                f.write(carbon_conf)
            # Write carbon storage-schemas
            with open(os.path.join('/opt/metrops', 'templates', 'storage-schemas.conf'), 'r') as f:
                storage_schemas_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'carbon', 'storage-schemas.conf'), 'w+') as f:
                f.write(storage_schemas_conf)
            # Write storage-aggregation
            with open(os.path.join('/opt/metrops', 'templates', 'storage-aggregation.conf'), 'r') as f:
                storage_aggregation_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'carbon', 'storage-aggregation.conf'), 'w+') as f:
                f.write(storage_aggregation_conf)
            # Add carbon instance to supervisord
            s.twiddler.addProgramToGroup('instances', 'carbon-%s' % instance, 
                    {'command':'/opt/graphite/bin/carbon-cache.py --config /opt/metrops/instances/%s/carbon/carbon.conf --debug start' % instance, 
                        'autostart':'true', 
                        'autorestart':'true', 
                        'startsecs':'0',
                        'stdout_logfile':'/opt/metrops/instances/%s/log/carbon-stdout.log' % instance,
                        'stdout_logfile_maxbytes':'1MB',
                        'stdout_logfile_backups':10,
                        'stdout_capture_maxbytes':'1MB',
                        'stderr_logfile':'/opt/metrops/instances/%s/log/carbon-stderr.log' % instance,
                        'stderr_logfile_maxbytes':'1MB',
                        'stderr_logfile_backups':10,
                        'stderr_capture_maxbytes':'1MB'
                    }
                )

            # Write graphite stuff, settings.py first
            with open(os.path.join('/opt/metrops', 'templates', 'settings.py'), 'r') as f:
                graphite_settings = f.read()
            graphite_settings = graphite_settings.format(
                        carbon_pickle_port = carbon_pickle_port,
                        secret_key = uuid.uuid4().get_hex()
                    )
            with open(os.path.join(self.base_path, instance, 'graphite', 'settings.py'), 'w+') as f:
                f.write(graphite_settings)
            # local-settings.py
            with open(os.path.join('/opt/metrops', 'templates', 'local_settings.py'), 'r') as f:
                graphite_local_settings = f.read()
            graphite_local_settings = string.Template(graphite_local_settings)
            graphite_local_settings = graphite_local_settings.substitute(
                        instance = instance,
                    )
            with open(os.path.join(self.base_path, instance, 'graphite', 'local_settings.py'), 'w+') as f:
                f.write(graphite_local_settings)
            # Dashboard
            with open(os.path.join('/opt/metrops', 'templates', 'dashboard.conf'), 'r') as f:
                dashboard_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'graphite', 'dashboard.conf'), 'w+') as f:
                f.write(dashboard_conf)
            # graphTemplates.conf
            with open(os.path.join('/opt/metrops', 'templates', 'graphTemplates.conf'), 'r') as f:
                graph_templates_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'graphite', 'graphTemplates.conf'), 'w+') as f:
                f.write(graph_templates_conf)
            # wsgi
            with open(os.path.join('/opt/metrops', 'templates', 'wsgi.py'), 'r') as f:
                graph_templates_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'graphite', 'wsgi.py'), 'w+') as f:
                f.write(graph_templates_conf)
            # __init__.py
            with open(os.path.join('/opt/metrops', 'templates', '__init__.py'), 'r') as f:
                graph_templates_conf = f.read()
            with open(os.path.join(self.base_path, instance, 'graphite', '__init__.py'), 'w+') as f:
                f.write(graph_templates_conf)
            shutil.copyfile(os.path.join('/opt/metrops/templates/graphite.db'),os.path.join(self.base_path, instance, 'storage', 'graphite.db'))
            s.twiddler.addProgramToGroup('instances', 'graphite-%s' % instance, 
                    {'command':'gunicorn wsgi:application -k gevent -b 127.0.0.1:%s' % graphite_port,
                        'directory': '/opt/metrops/instances/%s/graphite' % instance,
                        'autostart':'true', 
                        'autorestart':'true', 
                        'startsecs':'0',
                        'stdout_logfile':'/opt/metrops/instances/%s/log/graphite-stdout.log' % instance,
                        'stdout_logfile_maxbytes':'1MB',
                        'stdout_logfile_backups':10,
                        'stdout_capture_maxbytes':'1MB',
                        'stderr_logfile':'/opt/metrops/instances/%s/log/graphite-stderr.log' % instance,
                        'stderr_logfile_maxbytes':'1MB',
                        'stderr_logfile_backups':10,
                        'stderr_capture_maxbytes':'1MB'
                    }
                )
            
            self.used_slots += 1
            return {'instance': {
                                    'port': port, 
                                    'server': '127.0.0.1', 
                                    'instance': instance,
                                    'action': 'created'
                                }
                    }

    def delete_instance(self, instance):
        if os.path.exists(os.path.join(self.base_path, instance)):
            shutil.rmtree(os.path.join(self.base_path, instance))
            self.used_slots -= 1
            return {'instance': {'instance': instance, 'action': 'deleted'}}

def run(config, base_path="/opt/metrops/instances"):
    agent = zerorpc.Server(AgentApi(base_path=base_path))
    agent.bind("tcp://0.0.0.0:10042")
    agent.run()

if __name__=="__main__":
    print "Starting agent"
    run()
