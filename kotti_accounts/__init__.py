from __future__ import with_statement

from datetime import datetime

from UserDict import DictMixin

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import func
from sqlalchemy.sql.expression import or_
from sqlalchemy.orm.exc import NoResultFound

from pyramid.config import Configurator

from kotti import DBSession
from kotti import Base
from kotti.util import _
from kotti.util import request_cache

from kotti.events import objectevent_listeners
from kotti.security import get_principals
from kotti.security import Principal

from kotti_velruse.events import AfterKottiVelruseLoggedIn
from kotti_velruse.events import AfterLoggedInObject


log = __import__('logging').getLogger(__name__)


def kotti_configure(settings):
    # listen to events
    objectevent_listeners[
        (AfterKottiVelruseLoggedIn, AfterLoggedInObject)].append(after_login_handler)
    log.info(_(u'kotti_accounts configured'))


def _find_user(email):
    principals = get_principals()
    return principals.get(email)


def after_login_handler(event):
    log.debug('after_login_handler.object = {}'.format(event.object))
    obj = event.object

    #TODO: obtain info from obj.info, query database, create Principal/Account
    json = obj.json

    obj.identities = [ 'rgomes.info@gmail.com', 'rgomes1997@yahoo.co.uk' ]
    obj.principal = Principal(name='Richard Gomes', email='rgomes.info@gmail.com')
    obj.principal.last_login_date = datetime.now()
    obj.principal.id = 12345


class Account(Base):
    __tablename__ = 'accounts'
    __mapper_args__ = dict(
        order_by='accounts.email',
        )

    email = Column(Unicode(100), primary_key=True)
    uid = Column(Integer)

    def __init__(self, email, principal):
        self.email = email
        self.uid = principal.id

    def __repr__(self):  # pragma: no cover
        return '<Account %r>' % self.uid




class Accounts(DictMixin):
    """This class maps email addresses to a Principal.

    Accounts behaves as a proxy to Principals, coordinating how underlying Principals
    can be obtained from multiple extenally authenticated identities (identified by
    their email addresses).

    See: ``AbstractPrincipals`` for documentation.
    See: ``Principals`` for the wrapped implementation.

    Design decisions

    * associate multiple externally authenticated identities to a single Principal.
    * substitute part of the internal registration workflow provided by ``kotti.security``.
    * behave as a drop-in to the existing ``kotti.security`` Principals/
    * all existing test cases depending on Principals must pass.
    * integrate with `kotti_velruse`_ via events.

    Workflow

    In order to reuse the existing class kotti.security.Principals as it is, as well as
    reuse all existing code intended to perform authorization, this class does the following:

    * Maps a list of emails to an existing Principal.
    * As part of the login process, an externaly authenticated email (see: kotti_velruse) is
      informed to Accounts.
    * Accounts tries to find an association between an externally authenticated email and an
      existing Principal.
    * If an association is found, the corresponding Principal is returned.
    * If no association is found, a new Principal is automagically created, making sure that:
        * A unique username is "invented" on the fly. Note that the username is irrelevant
          from the user's perspective, since the user is uniquely identified by his/her
          externally authenticated email address.
        * The email address informed when a new Principal is created becomes the single point
          of contact with the user.
        * A random password is generated in order to increase security, just in case. Note
          that the nor the user nor this module needs to know the generated password at any
          time in future because authentication is always performed externally to Kotti.

    A principal can have multiple emails associated to it. This situation happens when an
    already logged in Principal authenticates externally again, providing a [possibly] new
    email address to Accounts. In this case:

    * When a new email is informed, a new association to the logged in Principal is created.
    * When an existing email is informed, there are two situations:
        * if already associated to the logged in Principal, nothing happens.
        * if already associated to another Principal, an error condition is raised.

    Pending

    1. Study how Principal.name or Principal.title are presented on different views by
       Kotti in general and by other plugins. Depending on circumstances, we will have
       to make something like: "principal.name = str(principal.id)" in order to make
       sure the name is unique. Eventually, we will have modify how principal.name is
       obtained, returning the title instead.
    """
    factory = Account

    def __init__(self, **kwargs):
        config = Configurator()

        config.add_

        settings = config.get_settings()
        self.stub_factory = settings.get(
            'kotti_accounts.stubs.principals_factory',
            'kotti.security.principals_factory')[0]().factory
        self.compatibility_mode = settings.get(
            'kotti_accounts.compatibility_mode', True)
        log.debug(type(self.stup_factory))
        log.debug(self.compatibility_mode)
        self.accounts_nodomain = '@nodomain'

    def name2email(self, name):
        return name if name.find('@') > -1 else name + self.accounts_nodomain

    @request_cache(lambda self, name: name)
    def __getitem__(self, name):
        name = unicode(name)
        try:
            account = DBSession.query(
                self.factory).filter(
                    self.factory.email == self.name2email(name)).one()
            return DBSession.query(
                self.stub_factory).filter(
                    self.stub_factory.id == account.id).one()
        except NoResultFound:
            raise KeyError(name)

    def __setitem__(self, name, principal):
        name = unicode(name)
        # an underlying Principal must be created when a dict is received
        if isinstance(principal, dict):
            principal = self.stub_factory(**principal)
            DBSession.add(principal)
        # create an Account associated to an existing Principal
        if isinstance(principal, self.stub_factory):
            account = self.factory(
                email=self.name2email(name), principal=principal)
            DBSession.add(account)
        else:
            raise AttributeError(type(principal))

    def __delitem__(self, name):
        name = unicode(name)
        try:
            principal = DBSession.query(
                self.factory).filter(self.factory.name == name).one()
            # deleting the Principal deletes all Account records 
            accounts = DBSession.query(
                self.factory).filter(self.factory.id == principal.id)
            for account in accounts:
                DBSession.delete(account)
        except NoResultFound:
            # deletes only one associated account, if any
            try:
                account = DBSession.query(
                    self.factory).filter(
                        self.factory.email == self.name2email(name)).one()
                DBSession.delete(account)
            except NoResultFound:
                raise KeyError(name)

    def iterkeys(self):
        if self.compatibility_mode:
            for (principal_name,) in DBSession.query(self.stub_factory.name):
                yield principal_name
        else:
            for (account_name,) in DBSession.query(self.factory.email):
                yield account_name

    def keys(self):
        return list(self.iterkeys())

    def search(self, **kwargs):
        if not kwargs:
            return []
        filters = []
        for key, value in kwargs.items():
            col = getattr(self.factory, key)
            if '*' in value:
                value = value.replace('*', '%').lower()
                filters.append(func.lower(col).like(value))
            else:
                filters.append(col == value)

        if self.compatibility_mode:
            query = DBSession.query(self.stub_factory)
        else:
            query = DBSession.query(self.factory)

        query = query.filter(or_(*filters))
        return query

    def hash_password(self, password, hashed=None):
        return self.stub_factory(password, hashed)

    def validate_password(self, clear, hashed):
        return self.stub_factory(clear, hashed)


def principals_factory():
    return Accounts()
