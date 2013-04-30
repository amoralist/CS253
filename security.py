import hmac
import random
import string
import hashlib

def hash_str(s):
    SECRET = 'farah'
    return hmac.new(SECRET,s).hexdigest()

def make_user_cookie(s):
    return "{0}|{1}".format(s, hash_str(s))

def check_user_cookie(h):
    vals = h.split("|")
    if hash_str(vals[0]) == vals[1]:
        return vals[0]
    else:
        return None

def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()

    return '%s|%s' % (h, salt)

def valid_pw(name, pw, h):
    check = make_pw_hash(name, pw, h.split('|')[1])

    return h == make_pw_hash(name, pw, check.split('|')[1])

def make_salt():
    return ''.join(random.choice(string.letters) for x in xrange(5))