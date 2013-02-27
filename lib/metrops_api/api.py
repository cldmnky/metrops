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
def error_response(code=404, message="Not found"):
    ret = {'errorResponse': {'code': 404, 'data': message}}
    resp = jsonify(ret)
    resp.status_code = 404
    return resp

@app.route("/api/accounts/", methods = ['GET', 'POST'])
@requires_basic_auth
def accounts_list():
    if request.method == "GET":
        try:
            user = db['users']
        except:
            return error_response(code=404, message="No such key")
        users = {}
        for user in db['users'].keys():
            users[user] = {}
            for k,v in db['users'][user].iteritems():
                users[user][k] = v
        data = {'accountsResponse': {'data': users, 'count': len(user)}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    elif request.method == "POST":
        # POST creates a user
        # 1. Generate  new uuid
        # 2. make a rpc call to one//all of the backends
        # 3. Decide on which backend to use
        # 4. Create the instance, get return from backend (host, ip, port, instance)
        u = uuid.uuid4()
        instance = rpc.create_instance(u)
        if instance.has_key('error'):
            return error_response(code=404, message=instance['error']['message']) 
        # Add instance to zodb
        try:
            db['users'][u.get_hex()] = Dict()
            db['users'][u.get_hex()]['dest'] = (instance['instance']['server'], instance['instance']['port'])
            db['users'][u.get_hex()]['password'] = uuid.uuid4().get_hex()
            db['users'][u.get_hex()]['server'] = instance['instance']['server']
        except Exception, e:
            print "Exception: %s" % e
        # Make a dict of the persistent obj
        user = {}
        for k ,v in db['users'][u.get_hex()].iteritems():
            user[k] = v
        data = {'accountsResponse': {'data': { u.get_hex() : user}, 'count': 1, 'action': 'created'}}
        type(data)
        resp = jsonify(data)
        resp.status_code = 200
        return resp



@app.route("/api/account/<string:uid>", methods = ['GET', 'POST', 'PUT', 'DELETE'])
@requires_basic_auth
def accounts(uid):
    if request.method == "GET":
        try:
            user = db['users'][uid]
        except:
            return error_response(code=404, message="No such account")
        user = {}
        for k,v in db['users'][uid].iteritems():
            user[k] = v
        data = {'accountsResponse': {'data': user, 'count': 1}}
        resp = jsonify(data)
        resp.status_code = 200
        return resp
    if request.method == "DELETE":
        try:
            user = db['users'][uid]
        except:
            return error_response(code=404, message="No such account")
        rpc_resp = rpc.delete_instance(uid)
        db['users'].pop(uid)
        transaction.commit()
        data = {'accountsResponse': {'data': {uid: {}}, 'count': 1, 'action': 'deleted'}}
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
