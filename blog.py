import webapp2
import jinja2
import os
import json
import urllib2
from string import letters
from datetime import datetime

from google.appengine.ext import db
from google.appengine.api import memcache

import functs
import security

import logging

# Probably ought to look into the capabilities/limitations of 
# jinja2 autoescaping.
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

class MainPage(Handler):
  def get(self):
      self.write('Hello, Udacity!')

# User signup/in pages

class User(db.Model):
    password = db.StringProperty(required=True)
    email = db.StringProperty(required=False)
    created = db.DateTimeProperty(auto_now_add=True)

class Signup(Handler):

    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        params = dict(username = username,
                      email = email)

        if not functs.valid_username(username):
            params['error_username'] = "That's not a valid username."
            have_error = True
        if not functs.valid_password(password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif password != verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True
        if not functs.valid_email(email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            key = db.Key.from_path('User', '{0}'.format(username))
            check = db.get(key)
            if check != None:
                params['error_username'] = "That username is taken, sorry."
                self.render('signup-form.html', **params)
            else:
                new_user = User(key_name= username, 
                                password= (security.make_pw_hash(username, password)),
                                email= email)
                new_user.put()
                self.response.headers.add_header('Set-Cookie', 'username={0}; Path=/'
                                        .format(security.make_user_cookie(username)))
                self.redirect('/welcome')

class Login(Handler):
    def get(self):
        self.render("login-form.html")

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        params = dict(username = username)

        user_key = db.Key.from_path('User', '{0}'.format(username))
        check = db.get(user_key)
        if check == None:
            params['error_username'] = "Incorrect user or password."
            self.render('login-form.html', **params)
        else:
            if security.valid_pw(username, password, check.password):
                self.response.headers.add_header('Set-Cookie', 'username={0}; Path=/'
                                        .format(security.make_user_cookie(username)))
                self.redirect('/welcome')
            else:
                params['error_username'] = "Incorrect user or password."
                self.render('login-form.html', **params)

class Logout(Handler):
    def get(self):
        self.response.headers.add_header('Set-Cookie', 
            'username=; Expires=Thu, 01-Jan-1970 00:00:00 GMT; Path=/')
        self.redirect('/blog/signup')

class Welcome(Handler):
    def get(self):
        cookie = self.request.cookies.get('username')
        if cookie:
            if security.check_user_cookie(cookie):
               self.render('welcome.html', username = cookie.split("|")[0])
        else:
            self.redirect('/blog/signup')



# Blog code

def blog_key(name = 'default'):
    return db.Key.from_path('blogs', name)

def front_page(update = False):
    key = 'top'
    key2 = 'time'
    page = memcache.get(key)
    qry_time = memcache.get(key2)
    if page is None or update:
        qry_time = datetime.now()
        logging.error("QUERY")
        page = db.GqlQuery("select * from Post order by created desc limit 10")
        memcache.set(key, page)
        memcache.set(key2, qry_time)
    return page, qry_time


class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)

    def render_post(response, post):
        response.out.write('<b>' + post.subject + '</b><br>')
        response.out.write(post.content)

    def render(self):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", p = self)

class BlogFront(Handler):
    def get(self):
        posts = front_page()[0]
        qry_time = front_page()[1]
        sec_ago = (datetime.now() - qry_time).seconds
        self.render('front.html', posts = posts, time_since_qry = sec_ago) 

class BlogFrontjson(Handler):
    def get(self):
        self.response.headers["Content-Type"] = 'application/json; charset=UTF-8'
        posts = front_page()[0]
        post_list = []
        for p in posts:
            d={}
            d['subject']=p.subject
            d['content']=p.content
            # Come back and figure how to represent DateTimes as strings
            # d['created']=p.created
            # d['las_modified']=p.last_modified
            post_list.append(d)
        post_list = json.dumps(post_list)
        self.write(post_list)

class NewPost(Handler):
    def get(self):
        self.render("newpost.html")

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post(parent = blog_key(), subject = subject, content = content)
            p.put()
            front_page(True)
            self.redirect('/blog/{0}'.format(str(p.key().id())))
        else:
            error = "subject and content, please!"
            self.render("newpost.html", subject=subject, content=content, error=error)

class PostPage(Handler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        qry_time = front_page()[1]
        sec_ago = (datetime.now() - qry_time).seconds
        self.render("permalink.html", post = post, time_since_qry = sec_ago)

class PostPagejson(Handler):
    def get(self, post_id):
        self.response.headers["Content-Type"] = 'application/json; charset=UTF-8'
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)
        if not post:
            self.error(404)
            return
        # See Problem Set 5 Answers for better method.
        d={}
        d['subject'] = post.subject
        d['content'] = post.content
        d = json.dumps(d)
        self.write(d)

class CacheFlush(Handler):
    def get(self):
        memcache.flush_all()
        self.redirect('/blog')

# ROT13 Code

class Rot13(Handler):
    def get(self):
        self.render('rot13-form.html')

    def post(self):
        rot13 = ''
        text = self.request.get('text')
        if text:
            rot13 = text.encode('rot13')

        self.render('rot13-form.html', text = rot13)


# See office hours 5-7 for more on pathing
app = webapp2.WSGIApplication([('/', MainPage),
                               ('/rot13', Rot13),
                               ('/welcome', Welcome),
                               ('/blog/?', BlogFront),
                               ('/blog/.json', BlogFrontjson),
                               ('/blog/signup', Signup),
                               ('/blog/login', Login),
                               # See Problem Set 5 Answers for better method
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/([0-9]+).json', PostPagejson),
                               ('/blog/flush', CacheFlush),
                               ('/blog/newpost', NewPost),
                               ('/blog/logout', Logout)
                               ],
                              debug=True)




















