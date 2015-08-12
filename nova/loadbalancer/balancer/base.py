# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo.config import cfg

from nova.loadbalancer import utils as lb_utils
from nova.openstack.common import importutils
from nova.scheduler import filters


lb_opts = [
    cfg.ListOpt('load_balancer_default_filters',
                default=[
                    'RetryFilter',
                    'AvailabilityZoneFilter',
                    'RealRamFilter',
                    'ComputeFilter',
                    'ComputeCapabilitiesFilter',
                    'ImagePropertiesFilter',
                    'ServerGroupAntiAffinityFilter',
                    'ServerGroupAffinityFilter',
                ],
                help='Which filter class names to use for filtering hosts '
                'when not specified in the request.')
]

CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer')
CONF.import_opt('scheduler_host_manager', 'nova.scheduler.driver')


class Base(object):

    def __init__(self, *args, **kwargs):
        super(Base, self).__init__(*args, **kwargs)
        self.host_manager = importutils.import_object(
            CONF.scheduler_host_manager)
        self.filter_handler = filters.HostFilterHandler()

    def balance(self, context, **kwargs):
        pass

    def filter_hosts(self, context, chosen_instance, nodes):
        filter_properties = lb_utils.build_filter_properties(context,
                                                             chosen_instance,
                                                             nodes)
        classes = self.host_manager.choose_host_filters(
            CONF.loadbalancer.load_balancer_default_filters)
        hosts = self.host_manager.get_all_host_states(context)
        filtered = self.filter_handler.get_filtered_objects(classes,
                                                            hosts,
                                                            filter_properties)
        return filtered, filter_properties
