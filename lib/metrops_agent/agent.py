#!/usr/bin/env python
# −*− coding: UTF−8 −*−
import zerorpc
import os
import socket
import shutil

class AgentApi(object):
    """ This is the Agent Api
    """
    def __init__(self, base_path="/opt/metrops/instances"):
        self.max_slots = 10
        self.base_path = base_path
        self.used_slots = self._get_used_slots()

    def get_slots(self):
        return {'slots': {
                            'max': self.max_slots, 
                            'free': self.max_slots - self.used_slots, 
                            'instances': self.get_instances()
                        }
                }
    def get_instances(self):
        return [ name for name in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, name)) ]

    def _get_used_slots(self):
        instances = self.get_instances()
        return len(instances)

    def create_instance(self, instance):
        if self.used_slots >= self.max_slots:
            return {'error': {'message': "Max slots reached"}}
        new_instance = os.path.dirname(os.path.join(self.base_path, instance))
        if not os.path.exists(os.path.join(self.base_path, instance)):
            os.makedirs(os.path.join(self.base_path, instance))
            # A lot more magic should happen here
            self.used_slots += 1
            return {'instance': {
                                    'port': 12345, 
                                    'server': '127.0.0.1', 
                                    'instance': instance,
                                    'action': 'created'
                                }
                    }

    def delete_instance(self, instance):
        if os.path.exists(os.path.join(self.base_path, instance)):
            shutil.rmtree(os.path.join(self.base_path, instance))
            self.used_slots - 1
            return {'instance': {'instance': instance, 'action': 'deleted'}}

def run(base_path):
    agent = zerorpc.Server(AgentApi(base_path=base_path))
    agent.bind("tcp://0.0.0.0:10042")
    agent.run()

if __name__=="__main__":
    print "Starting agent"
    run("instances")
