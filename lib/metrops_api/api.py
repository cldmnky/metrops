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
from flask.ext.zodb import ZODB, Dict, transaction
from flask import jsonify
from lib.basicauth import *
import lib.rpc as rpc

app = Flask(__name__)

app.config['ZODB_STORAGE'] = 'zeo://localhost:8090'

db = ZODB(app)

auth_users = ['admin:admin']


def make_salted_pass(password):
    salt = os.urandom(4)
    h = hashlib.sha1(password)
    h.update(salt)
    return "{SSHA}" + encode(h.digest() + salt)

@app.before_request
def set_db_defaults():
    if 'basic_auth' not in db:
        db['basic_auth'] = auth_users
    elif 'users' not in db:
        db['users'] = Dict()


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
            user = db['users']
        except:
            return error_response_404(code=404, message="No such key")
        users = {}
        for user in db['users'].keys():
            users[user] = {}
            for k,v in db['users'][user].iteritems():
                users[user][k] = v
        data = {'instancesResponse': {'data': users, 'count': len(user)}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    elif request.method == "POST":
        # POST creates a user
        # 1. Generate  new uuid
        # 2. make a rpc call to one//all of the backends
        # 3. Decide on which backend to use
        # 4. Create the instance, get return from backend (host, ip, port, instance)
        account = request.form['account']
        u = uuid.uuid4()
        instance = rpc.create_instance(u)
        if instance.has_key('error'):
            return error_response_500(code=500, message=instance['error']['message']) 
        # Add instance to zodb
        try:
            db['users'][u.get_hex()] = Dict()
            db['users'][u.get_hex()]['dest'] = (instance['instance']['server'], instance['instance']['port'])
            db['users'][u.get_hex()]['password'] = uuid.uuid4().get_hex()
            db['users'][u.get_hex()]['server'] = instance['instance']['server']
            db['users'][u.get_hex()]['account'] = account
        except Exception, e:
            print "Exception: %s" % e
        # Make a dict of the persistent obj
        user = {}
        for k ,v in db['users'][u.get_hex()].iteritems():
            user[k] = v
        data = {'instanceResponse': {'data': { u.get_hex() : user}, 'count': 1, 'action': 'created'}}
        type(data)
        resp = jsonify(data)
        resp.status_code = 200
        return resp



@app.route("/api/instance/<string:uid>", methods = ['GET', 'POST', 'PUT', 'DELETE'])
@requires_basic_auth
def instance(uid):
    if request.method == "GET":
        try:
            user = db['users'][uid]
        except:
            return error_response_404(code=404, message="No such account")
        user = {}
        for k,v in db['users'][uid].iteritems():
            user[k] = v
        data = {'instanceResponse': {'data': user, 'count': 1}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    if request.method == "DELETE":
        try:
            user = db['users'][uid]
        except:
            return error_response_404(code=404, message="No such instance")
        rpc_resp = rpc.delete_instance(uid)
        db['users'].pop(uid)
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
