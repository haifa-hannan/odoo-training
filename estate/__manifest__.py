{
    "name": "Estate",  # The name that will appear in the App list
    "version": "16.0.0",  # Version
    "author": "Haifa",
    "application": True,  # This line says the module is an App, and not a module
    "depends": ["base"],  # dependencies
    "data": [
        'security/ir.model.access.csv',
        'views/estate_property_offers.xml',
        'views/estate_property_tags.xml',
        'views/estate_property_type.xml',
        'views/estate_property.xml',
        'views/res_user.xml',
        'views/estate_menus.xml',
    ],
    "installable": True,
    'application': True,
    'license': 'LGPL-3',
}
