#!/usr/bin/env python
# −*− coding: UTF−8 −*−
import hashlib
import os
import uuid
import zerorpc
from gevent import monkey
monkey.patch_all()
from base64 import urlsafe_b64encode as encode
from base64 import urlsafe_b64decode as decode
from flask import Flask
from flask.ext.zodb import ZODB, Dict, transaction, List
from flask import jsonify
from lib.basicauth import *
import lib.rpc as rpc

app = Flask(__name__)

app.config['ZODB_STORAGE'] = 'zeo://localhost:8090'

db = ZODB(app)

auth_users = ['admin:%s' % make_salted_pass('admin')]

# Initialize db
with app.test_request_context():
    if 'basic_auth' not in db:
        db['basic_auth'] = List()
        db['basic_auth'] = auth_users
    elif 'instances' not in db:
        db['instances'] = Dict()


@app.before_request
def set_db_defaults():
    if 'basic_auth' not in db:
        db['basic_auth'] = List()
        db['basic_auth'] = auth_users
    elif 'instances' not in db:
        db['instances'] = Dict()


@app.errorhandler(404)
def error_response_404(code=404, message="Not Found"):
    ret = {'errorResponse': {'code': 404, 'data': message}}
    resp = jsonify(ret)
    resp.status_code = 404
    return resp

@app.errorhandler(401)
def error_response_401(code=401, message="Bad Request"):
    ret = {'errorResponse': {'code': 401, 'data': message}}
    resp = jsonify(ret)
    resp.status_code = 401
    return resp

@app.errorhandler(500)
def error_response_500(code=500, message="Internal Server Error"):
    ret = {'errorResponse': {'code': 500, 'data': message}}
    resp = jsonify(ret)
    resp.status_code = 500
    return resp

@app.route("/api/instances/", methods = ['GET', 'POST'])
@requires_basic_auth
def instances_list():
    if request.method == "GET":
        try:
            instance = db['instances']
        except:
            return error_response_404(code=404, message="No such key")
        instances = {}
        for instance in db['instances'].keys():
            instances[instance] = {}
            for k,v in db['instances'][instance].iteritems():
                instances[instance][k] = v
        data = {'instancesResponse': {'data': instances, 'count': len(instances)}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    elif request.method == "POST":
        # POST creates a instance
        # 1. Generate  new uuid
        # 2. make a rpc call to one//all of the backends
        # 3. Decide on which backend to use
        # 4. Create the instance, get return from backend (host, ip, port, instance)
        account = request.form['account']
        u = uuid.uuid4()
        password = uuid.uuid4().get_hex()
        instance = rpc.create_instance(u, password)
        if instance.has_key('error'):
            return error_response_500(code=500, message=instance['error']['message']) 
        # Add instance to zodb
        print "Save to db"
        try:
            db['instances'][u.get_hex()] = Dict()
            db['instances'][u.get_hex()]['dest'] = (instance['instance']['server'], instance['instance']['port'])
            db['instances'][u.get_hex()]['password'] = password
            db['instances'][u.get_hex()]['server'] = instance['instance']['server']
            db['instances'][u.get_hex()]['account'] = account
        except:
            print "Exception"
        # Make a dict of the persistent obj
        instance = {}
        for k ,v in db['instances'][u.get_hex()].iteritems():
            instance[k] = v
        data = {'instanceResponse': {'data': { u.get_hex() : instance}, 'count': 1, 'action': 'created'}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp



@app.route("/api/instance/<string:uid>", methods = ['GET', 'POST', 'PUT', 'DELETE'])
@requires_basic_auth
def instance(uid):
    if request.method == "GET":
        try:
            instance = db['instances'][uid]
        except:
            return error_response_404(code=404, message="No such account")
        instance = {}
        for k,v in db['instances'][uid].iteritems():
            instance[k] = v
        data = {'instanceResponse': {'data': instance, 'count': 1}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    if request.method == "DELETE":
        try:
            instance = db['instances'][uid]
        except:
            return error_response_404(code=404, message="No such instance")
        rpc_resp = rpc.delete_instance(uid)
        instance = db['instances'].pop(uid)
        transaction.commit()
        data = {'instanceResponse': {'data': {uid: {}}, 'count': 1, 'action': 'deleted'}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp

@app.route("/api/stats/", methods = ['GET'])
@requires_basic_auth
def stats():
    if request.method == "GET":
        pass

if __name__ == "__main__":
    app.run(debug=True)
