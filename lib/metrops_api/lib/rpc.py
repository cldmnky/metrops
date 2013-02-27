#!/usr/bin/env python
# −*− coding: UTF−8 −*−
import uuid
import zerorpc


def rpc_client():
    client = zerorpc.Client()
    client.connect("tcp://localhost:10042")
    return client

def create_instance(uid):
    client = rpc_client()
    instance = client.create_instance(uid.get_hex())
    return instance

def delete_instance(instance):
    client = rpc_client()
    rpc_resp = client.delete_instance(instance)
    return rpc_resp
