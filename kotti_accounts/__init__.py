import sys

from pprint import pformat

from datetime import datetime

from UserDict import DictMixin

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import func
from sqlalchemy.sql.expression import or_
from sqlalchemy.orm.exc import NoResultFound

from kotti import DBSession
from kotti import Base
from kotti.util import _
from kotti import get_settings
from kotti.util import request_cache
from kotti.events import objectevent_listeners
from kotti.events import notify
from kotti.security import USER_MANAGEMENT_ROLES
from kotti.security import get_principals
from kotti.views.login import UserSelfRegistered
from kotti_velruse.events import AfterKottiVelruseLoggedIn
from kotti_velruse.events import AfterLoggedInObject

__version__ = '0.2.3'

log = __import__('logging').getLogger(__name__)


def kotti_configure(settings):
    kotti_configure_events(settings)
    kotti_configure_views(settings)
    log.info('{} configured'.format(__name__))


def kotti_configure_events(settings):
    objectevent_listeners[
        (AfterKottiVelruseLoggedIn, AfterLoggedInObject)].append(
            after_login_handler)


def kotti_configure_views(settings):
    settings['pyramid.includes'] += ' kotti_accounts.views'


def after_login_handler(event):
    log.debug('after_login_handler.object = {}'.format(event.object))
    (event.object.principal, event.object.identities) = find_principal(event.object.json,
                                                                       event.object.user,
                                                                       event.object.request)


def _find_user(email):
    principals = get_principals()
    return principals.get(email)


def find_principal(json, user, request):
    #-- log.debug('find_principal {}'.format(pformat(json)))
    displayName = None
    verifiedEmail = None
    emails = []
    if 'profile' in json:
        profile = json['profile']
        if 'emails' in profile:
            emails = profile['emails']
        if 'verifiedEmail' in profile:
            verifiedEmail = profile['verifiedEmail']
        elif len(emails) > 0:
            verifiedEmail = emails[0]
        if verifiedEmail is None:
            raise AttributeError(_(u'Provider have not informed any email address'))
        if 'displayName' in profile:
            displayName = profile['displayName']
        elif 'name' in profile and 'formatted' in profile['name']:
            displayName = profile['name']['formatted']
        else:
            displayName = verifiedEmail

    accounts   = Accounts()

    if user is None:
        try:
            log.debug('Find Principal for email {}'.format(verifiedEmail))
            principal = accounts[verifiedEmail]
        except Exception as e:
            log.debug('Exception {}'.format(type(e)))
            log.debug('Create Principal {} for email {}'.format(displayName, verifiedEmail))
            accounts[verifiedEmail] = {
                'name' : verifiedEmail,
                'title': displayName,
                'email': verifiedEmail
                }
            # creates a new Principal
            principal = accounts[verifiedEmail]
            # assing administration rights to it, ONLY IF needed
            admins = get_settings().get('kotti.accounts.admins')
            if admins and verifiedEmail in admins:
                log.warn('New Principal {} for email {} has got ADMINISTRATIVE RIGHTS !!!'.format(
                    displayName, verifiedEmail))
                principal.groups = USER_MANAGEMENT_ROLES
            # Triggers UserSelfRegistered event in case user is None, i.e: when a true
            # new user registers, not when a new email is added to an existing account.
            notify(UserSelfRegistered(principal, request))
    else:
        principal = user
        log.debug('verifiedEmail is {}'.format(verifiedEmail))
        log.debug('principal is {}'.format(principal))
        log.debug(type(principal))
        try:
            dummy = accounts[verifiedEmail]
        except Exception as e:
            accounts[verifiedEmail] = principal

    for email in emails:
        if email != verifiedEmail:
            log.debug('Create additional Account for email {}'.format(email))
            try:
                dummy = accounts[email]
            except:
                accounts[email] = principal

    principal.last_login_date = datetime.now()
    return (principal, emails)




class Account(Base):
    __tablename__ = 'accounts'
    __mapper_args__ = dict(
        order_by='accounts.email',
        )

    email = Column(Unicode(100), primary_key=True)
    id = Column(Integer)

    def __init__(self, email, id):
        self.email = email
        self.id = id

    def __repr__(self):  # pragma: no cover
        return '<Account %r>' % self.id




class Accounts(DictMixin):
    """This class maps email addresses to a Principal.

    Accounts behaves as a proxy to Principals, coordinating how underlying Principals
    can be obtained from multiple extenally authenticated identities (identified by
    their email addresses).

    See: ``AbstractPrincipals`` for documentation.
    See: ``Principals`` for the wrapped implementation.

    Design
    ------

    * associate multiple externally authenticated identities to a single Principal.
    * substitute part of the internal registration workflow provided by ``kotti.security``.
    * behave as a drop-in to the existing ``kotti.security`` Principals/
    * all existing test cases depending on Principals must pass.
    * integrate with `kotti_velruse`_ via events.

    Workflow
    --------

    In order to reuse the existing class kotti.security.Principals as it is, as well as
    reuse all existing code intended to perform authorization, this class does the following:

    * Maps a list of emails to an existing Principal.
    * As part of the login process, an externaly authenticated email (see: kotti_velruse) is
      informed to Accounts.
    * Accounts tries to find an association between an externally authenticated email and an
      existing Principal.
    * If an association is found, the corresponding Principal is returned.
    * If no association is found, a new Principal is automagically created, making sure that:
        * A unique username is obtained from the verified email informed by the authentication
          provider. This is done in the hope that email is a good unique key and for the sake
          of compatibility with the existing implementation of kotti.security.Principals.
        * A new Account is created with primary key defined by the verified email informed by
          the authentication provider.
        * In case the authentication provider returns a list of emails, a list of Account
          records is created and associated to the Principal just created.

    Multiple Account records can be associated to a single Principals. One situation was
    already described above. Another situation happens when an already logged in Principal
    authenticates externally again, providing a [possibly] new email address to Accounts.
    In this case:

    * When a new email is informed, a new association to the logged in Principal is created.
    * When an existing email is informed, there are two situations:
        * if already associated to the logged in Principal, nothing happens.
        * if already associated to another Principal, an error condition is raised.

    Still, another possibility of multiple email addresses associated to a single Principal
    arises when principals are merged. In this case, one of them is simply discarded and
    all resources associated to it are migrated to the remaining Principal.

    Pending
    -------

    1. Substitute hardcode in __init__ so that stub_principals and stub_factory are obtained
       from configuration.

    2. Implement merging of Principals;
    """

    factory = Account
    stub_principals = None
    stub_factory = None
    nodomain = '@localdomain'


    def __init__(self, behave_as_Principals=True):
        import kotti.security
        self.stub_principals = kotti.security.Principals()
        self.stub_factory = self.stub_principals.factory
        self.behave_as_Principals = behave_as_Principals


    @request_cache(lambda self, name: name)
    def __getitem__(self, name):
        log.debug( sys._getframe().f_code.co_name )
        log.debug(type(name))
        log.debug(name)
        name = unicode(name)
        try:
            principal = DBSession.query(
                self.stub_factory).filter(
                    self.stub_factory.name == name).one()
            log.debug('principal found :: id={} name={} email={}'.format(
                principal.id, principal.name, principal.email))
            return principal
        except NoResultFound:
            try:
                account = DBSession.query(
                    self.factory).filter(
                        self.factory.email == self.__name2email(name)).one()
                log.debug('account found  id={} email={}'.format(
                    account.id, account.email))
                principal = DBSession.query(
                    self.stub_factory).filter(
                        self.stub_factory.id == account.id).one()
                log.debug('principal found :: id={} name={} email={}'.format(
                    principal.id, principal.name, principal.email))
                return principal
            except NoResultFound:
                log.error('KeyError')
                raise KeyError(name)


    def __setitem__(self, name, principal):
        log.debug( sys._getframe().f_code.co_name )
        name = unicode(name)
        if isinstance(principal, dict):
            log.debug('Creating Principal\n{}'.format(pformat(principal)))
            principal = self.stub_factory(**principal)
            log.debug(type(principal))
            log.debug('adding Principal')
            DBSession.add(principal)
            log.debug('flush')
            DBSession.flush()
            log.debug('Principal added :: id={} email={}'.format(principal.id, principal.email))
        if isinstance(principal, self.stub_factory):
            log.debug('Creating Account id={}  email={}'.format(principal.id, name))
            account = self.factory(email=name, id=principal.id)
            log.debug('adding Account')
            DBSession.add(account)
            log.debug('Account added :: id={} email={}'.format(account.id, account.email))
        else:
            raise AttributeError(name)


    def __delitem__(self, name):
        log.debug( sys._getframe().f_code.co_name )
        if self.behave_as_Principals:
            del self.stub_factory[name]
        else:
            name = unicode(name)
            log.debug(name)
            account = DBSession.query(
                self.factory).filter(self.factory.email == name).one()
            DBSession.delete(account)


    def iterkeys(self):
        log.debug( sys._getframe().f_code.co_name )
        if self.behave_as_Principals:
            for principal_name in self.stub_factory.iterkeys():
                yield principal_name
        else:
            for (account_name,) in DBSession.query(self.factory.email):
                yield account_name


    def keys(self):
        log.debug( sys._getframe().f_code.co_name )
        return list(self.iterkeys())


    def search(self, **kwargs):
        log.debug( sys._getframe().f_code.co_name )
        if self.behave_as_Principals:
            return self.stub_factory.search(kwargs)

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

        query = DBSession.query(self.factory)
        query = query.filter(or_(*filters))
        return query


    def hash_password(self, password, hashed=None):
        log.debug( sys._getframe().f_code.co_name )
        return self.stub_principals.hash_password(password, hashed)


    def validate_password(self, clear, hashed):
        log.debug( sys._getframe().f_code.co_name )
        return self.stub_principals.validate_password(clear, hashed)

    def __name2email(self, name):
        return name if name.find('@') > -1 else name + self.nodomain



def principals_factory():
    return Accounts()
