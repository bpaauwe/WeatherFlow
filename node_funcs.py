#
#  Common functions used by nodes


try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface


LOGGER = polyinterface.LOGGER

"""
    Some common functions to be used by node servers

    To add these functions call the add_functions_as_methods()
    function.  Then the functions specified in 'functions' below
    will be available for use as if they were defined in the node's
    primary class.
"""
def add_functions_as_methods(functions):
    def decorator(Class):
        for function in functions:
            setattr(Class, function.__name__, function)
        return Class
    return decorator


# Wrap all the setDriver calls so that we can check that the 
# value exist first.
def update_driver(self, driver, value, force=False, prec=3):
    try:
        self.setDriver(driver, round(float(value), prec), True, force, self.uom[driver])
        LOGGER.debug('setDriver (%s, %f)' %(driver, float(value)))
    except:
        LOGGER.warning('Missing data for driver ' + driver)

def get_saved_log_level(self):
    if 'customData' in self.polyConfig:
        if 'level' in self.polyConfig['customData']:
            return self.polyConfig['customData']['level']

    return 0

def save_log_level(self, level):
    level_data = {
            'level': level,
            }
    self.poly.saveCustomData(level_data)

def set_logging_level(self, level=None):
    if level is None:
        try:
            level = self.get_saved_log_level()
        except:
            LOGGER.error('set_logging_level: get saved log level failed.')

        if level is None:
            level = 30
        level = int(level)
    else:
        level = int(level['value'])

    self.save_log_level(level)

    LOGGER.info('set_logging_level: Setting log level to %d' % level)
    LOGGER.setLevel(level)

functions = (update_driver, get_saved_log_level, save_log_level, set_logging_level)

"""
    Functions to handle custom parameters.

    pass in a list of name and default value parameters
    [
        {'name': name of parameter,
         'default': default value of parameter,
         'notice': 'string to send notice if not set',
         'isRequired: True/False,
        },
        {'name': name of parameter,
         'default': default value of parameter,
         'notice': 'string to send notice if not set',
         'isRequired: True/False,
        },
    ]

    usage:
       self.params = NSParameters(param_list)
       self.params.get('param1')
       if self.params.isSet('param1'):

"""

class NSParameters:
    def __init__(self, parameters):
        self.internal = []

        for p in parameters:
            self.internal.append({
                'name': p['name'],
                'value': '', 
                'default': p['default'],
                'isSet': False,
                'isRequired': p['isRequired'],
                'notice_msg': p['notice'],
                })

    def set(self, name, value):
        for p in self.internal:
            if p['name'] == name:
                p['value'] = value
                p['isSet'] = True
                return

    def get(self, name):
        for p in self.internal:
            if p['name'] == name:
                if p['isSet']:
                    return p['value']
                else:
                    return p['default']

    def isSet(self, name):
        for p in self.internal:
            if p['name'] == name:
                return p['isSet']
        return False

    """
        Send notices for unconfigured parameters that are are marked
        as required.
    """
    def send_notices(self, poly):
        for p in self.internal:
            if not p['isSet'] and p['isRequired']:
                if p['notice_msg'] is not None:
                    poly.addNotice(p['notice_msg'], p['name'])

    """
        Read paramenters from Polyglot and update values appropriately.

        return True if all required parameters are set to non-default values
        otherwise return False
    """
    def get_from_polyglot(self, poly):
        customParams = poly.polyConfig['customParams']
        params = {}

        for p in self.internal:
            LOGGER.debug('checking for ' + p['name'] + ' in customParams')
            if p['name'] in customParams:
                LOGGER.debug('found ' + p['name'] + ' in customParams')
                p['value'] = customParams[p['name']]
                if p['value'] != p['default']:
                    LOGGER.debug(p['name'] + ' is now set')
                    p['isSet'] = True
            
            if p['isSet']:
                params[p['name']] = p['value']
            else:
                params[p['name']] = p['default']

        poly.addCustomParam(params)            

        for p in self.internal:
            if not p['isSet'] and p['isRequired']:
                return False
        return True


    """
        Called from process_config to check for configuration change
        We need to know two things; 1) did the configuration change and
        2) are all required fields filled in.
    """
    def update_from_polyglot(self, config):
        changed = False
        valid = True

        if 'customParams' in config:
            for p in self.internal:
                if p['name'] in config['customParams']:
                    poly_param = config['customParams'][p['name']]

                    # did it change?
                    if poly_param != p['default'] and poly_param != p['value']:
                        changed = True

                    # is it different from the default?
                    if poly_param != p['default']:
                        p['value'] = poly_param
                        p['isSet'] = True

        for p in self.internal:
            if not p['isSet'] and p['isRequired']:
                valid = False

        return (valid, changed)


