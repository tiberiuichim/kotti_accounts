| Code_ | Bugs_ | Forum_ | Docs_ | License_ | Contact_

.. _Code : http://github.com/frgomes/kotti_accounts
.. _Bugs : http://github.com/frgomes/kotti_accounts/issues
.. _Forum : http://github.com/frgomes/kotti_accounts/wiki
.. _Docs : http://kotti_accounts.readthedocs.org
.. _License : http://opensource.org/licenses/BSD-3-Clause
.. _Contact : http://github.com/~frgomes


`kotti_accounts`_ is a `Kotti`_ plugin which allows a user principal to be associated to
multiple email accounts.

`Find out more about Kotti`_

.. _`Kotti`: http://pypi.python.org/pypi/Kotti
.. _`Find out more about Kotti`: http://pypi.python.org/pypi/Kotti
.. _`kotti_velruse`: http://pypi.python.org/pypi/kotti_velruse
.. _`kotti_accounts`: http://pypi.python.org/pypi/kotti_accounts


.. note:: THIS IS A PREVIEW VERSION of `kotti_accounts`_, which is primarily intended to
          allow `kotti_velruse`_ create a fake user credential in the current browser
          session.


Setup
=====

1. Insert ``kotti_accounts.kotti_configure`` on ``kotti.configurators``

    kotti.configurators = kotti_tinymce.kotti_configure
                          kotti_velruse.kotti_configure
                          kotti_accounts.kotti_configure


Design Decisions
================

* associate multiple externally authenticated identities to a single Principal.
* substitute part of the internal registration workflow provided by ``kotti.security``.
* behave as a drop-in to the existing ``kotti.security`` Principals/
* all existing test cases depending on Principals must pass.
* integrate with `kotti_velruse`_ via events.

Workflow
========

* The first time a user authenticates with an OpenID account (or any other
  authentication method), a new account is allocated and the extenal email obtained
  at authentication time is associated to the uid which uniquely identifies the
  allocated account.

Future workflows:

* (TODO) The user is able to associate additional authenticated emails to his/her
  existing account. In order to do this, an already logged in user authenticates
  again with another authentication provider. If the authentication succeeds and
  the external email is not existent in the database, then it is associated to the
  account of the logged in user.

* (TODO) ability to remove emails from an account. Removing the last email removes
  the account and all its associated resources permanently.

* (TODO) ability to merge accounts.


How it works
============

Documentation is pending.

