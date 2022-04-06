Setting Up a Production Sidechain
=================================

A production sidechain is a sidechain where each federator is running on a separate server.
This sidechain is production-ready and set up for external people to access it.


Set up servers
--------------

Set up a server for each federator you want to run.

.. TODO: figure out server needs
.. relevant link: https://xrpl.org/system-requirements.html


Setting up environment variables
--------------------------------

This hasn't been quite implemented yet - you have to do it by hand a bit.


Setting up config files
-----------------------

Run ``sidechain-config``


Starting up a sidechain
-----------------------

Spin up the federator servers.

.. TODO: add CLI args to make this easier

Run `slk.chain.chain_setup.setup_prod_mainchain` with the appropriate variables.

Run `slk.chain.chain_setup.setup_prod_sidechain` with the appropriate variables.
