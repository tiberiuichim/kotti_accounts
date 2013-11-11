import sys

from pyramid.httpexceptions import HTTPNotFound
from pyramid.exceptions import Forbidden
from pyramid.request import Request
from pyramid.security import remember

from kotti import DBSession
from kotti.util import _
from kotti.views.util import template_api
from kotti.views.util import is_root

from kotti_accounts import Accounts


log = __import__('logging').getLogger(__name__)


def includeme(config):
    # override @@prefs
    config.add_view(name='prefs',
                    view='kotti_accounts.views.Preferences',
                    custom_predicates=( is_root, ),
                    renderer='kotti_accounts:templates/edit/accounts.pt')
    log.info('{} configured'.format(__name__))



class Preferences(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.flash = self.request.session.flash


    def __call__(self):
        log.debug( sys._getframe().f_code.co_name )
        user = self.request.user
        if user is None:
            raise Forbidden()

        accounts = Accounts(behave_as_Principals=False)
        principals = accounts.stub_principals

        try:
            if 'change' in self.request.POST:
                name = self.request.POST['name']
                log.debug('change name "{}"'.format(name))
                principal       = principals[user.email]
                principal.title = name
                DBSession.add(principal)
            elif 'promote' in self.request.POST:
                promote = self.request.POST['promote']
                log.debug('promote email {}'.format(promote))
                # swap emails between principal and account
                log.debug('swap emails between principal and account')
                account         = accounts[promote]
                account.email   = user.email
                principal       = principals[user.email]
                principal.name  = promote
                principal.email = promote
                user.email      = promote
                log.debug('update account   id={} email={}'.format(account.id, account.email))
                DBSession.add(account)
                log.debug('update principal id={}  name={}'.format(principal.id, principal.name))
                DBSession.add(principal)
                remember(self.request, principal.name)
            elif 'delete' in self.request.POST:
                email = self.request.POST['delete']
                log.debug('delete email {}'.format(email))
                del accounts[email]
            elif 'add' in self.request.POST:
                log.debug('add')
                redirect = Request.blank('{}?{}={}'.format(
                    self.request.application_url + '/@@login',
                    'came_from', self.request.application_url + '/@@prefs'))
                response = self.request.invoke_subrequest( redirect )
                return response
            else:
                log.debug('---> NONE')
        except Exception as e:
            message = e.message
            log.exception(_(u'{}\nStacktrace follows:\n{}').format(message, e))
            raise HTTPNotFound(message).exception

        principal = principals[user.email]
        log.debug('principal = {}'.format(principal))
        secondary = list()
        for account in accounts.search(id=str(user.id)):
            if account.email != principal.email:
                secondary.append(account)
                log.debug('account id={}  email={}'.format(account.id, account.email))

        api = template_api(self.context, self.request)
        api.page_title = _(u"My preferences - ${title}",
                           mapping=dict(title=api.site_title))

        return {
            'api': api,
            'principal' : principal,
            'accounts'  : secondary
            }
