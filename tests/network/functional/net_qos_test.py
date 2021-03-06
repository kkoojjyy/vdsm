# Copyright 2017-2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division

import pytest

from .netfunctestlib import NetFuncTestAdapter, NOCHK
from network.nettestlib import dummy_device

NETWORK1_NAME = 'test-network1'
NETWORK2_NAME = 'test-network2'
VLAN1 = 10
VLAN2 = 20
_100USEC = 100 * 1000

adapter = None


@pytest.fixture(scope='module', autouse=True)
def create_adapter(target):
    global adapter
    adapter = NetFuncTestAdapter(target)


# TODO: When QoS will be available on OVS, enable the tests.
@pytest.mark.parametrize('switch', [pytest.mark.legacy_switch('legacy')])
class TestNetworkHostQos(object):

    def test_add_vlan_network_with_qos(self, switch):
        HOST_QOS_CONFIG = {'out': {'ls': {'m1': rate(rate_in_mbps=4),
                                          'd': _100USEC,
                                          'm2': rate(rate_in_mbps=3)},
                                   'ul': {'m2': rate(rate_in_mbps=8)}}}
        with dummy_device() as nic:
            NETCREATE = {NETWORK1_NAME: {'nic': nic, 'vlan': VLAN1,
                                         'hostQos': HOST_QOS_CONFIG,
                                         'switch': switch}}
            with adapter.setupNetworks(NETCREATE, {}, NOCHK):
                adapter.assertHostQos(NETWORK1_NAME,
                                      NETCREATE[NETWORK1_NAME])

    def test_add_two_networks_with_qos_on_shared_nic(self, switch):
        HOST_QOS_CONFIG1 = {'out': {'ls': {'m2': rate(rate_in_mbps=1)}}}
        HOST_QOS_CONFIG2 = {'out': {'ls': {'m2': rate(rate_in_mbps=5)}}}
        with dummy_device() as nic:
            NETCREATE = {NETWORK1_NAME: {'nic': nic,
                                         'hostQos': HOST_QOS_CONFIG1,
                                         'switch': switch},
                         NETWORK2_NAME: {'nic': nic, 'vlan': VLAN1,
                                         'hostQos': HOST_QOS_CONFIG2,
                                         'switch': switch}}
            with adapter.setupNetworks(NETCREATE, {}, NOCHK):
                adapter.assertHostQos(NETWORK1_NAME,
                                      NETCREATE[NETWORK1_NAME])
                adapter.assertHostQos(NETWORK2_NAME,
                                      NETCREATE[NETWORK2_NAME])

    def test_add_two_networks_with_qos_on_shared_nic_in_two_steps(self,
                                                                  switch):
        HOST_QOS_CONFIG1 = {'out': {'ls': {'m2': rate(rate_in_mbps=1)}}}
        HOST_QOS_CONFIG2 = {'out': {'ls': {'m2': rate(rate_in_mbps=5)}}}
        with dummy_device() as nic:
            NETBASE = {NETWORK1_NAME: {'nic': nic,
                                       'hostQos': HOST_QOS_CONFIG1,
                                       'switch': switch}}
            NETVLAN = {NETWORK2_NAME: {'nic': nic, 'vlan': VLAN1,
                                       'hostQos': HOST_QOS_CONFIG2,
                                       'switch': switch}}
            with adapter.setupNetworks(NETBASE, {}, NOCHK):
                with adapter.setupNetworks(NETVLAN, {}, NOCHK):
                    adapter.assertHostQos(NETWORK1_NAME,
                                          NETBASE[NETWORK1_NAME])
                    adapter.assertHostQos(NETWORK2_NAME,
                                          NETVLAN[NETWORK2_NAME])


def rate(rate_in_mbps):
    return rate_in_mbps * 1000 ** 2
