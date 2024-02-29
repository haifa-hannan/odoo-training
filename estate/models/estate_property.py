from datetime import timedelta, datetime
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

class EstateProperty(models.Model):
    _name = "estate.property"
    _description = "Real Estate Property"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    postcode = fields.Char(string="Postcode")
    date_availability = fields.Date(string="Availability Date", copy=False, default=lambda self: fields.Date.today() + timedelta(days=90))
    expected_price = fields.Float(string="Expected Price", required=True)
    selling_price = fields.Float(string="Selling Price", readonly=True)
    bedrooms = fields.Integer(string="Bedrooms", default=2)
    living_area = fields.Integer(string="Living Area (sqm)")
    facades = fields.Integer(string="Number of Facades")
    garage = fields.Boolean(string="Garage")
    garden = fields.Boolean(string="Garden")
    garden_area = fields.Integer(string="Garden Area (sqm)")
    garden_orientation = fields.Selection([
        ('North', 'North'),
        ('South', 'South'),
        ('East', 'East'),
        ('West', 'West')
    ], string="Garden Orientation")
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([
        ('New','New'), 
        ('Offer Received','Offer Received'),
        ('Offer Accepted','Offer Accepted'),
        ('Sold','Sold'),
        ('Canceled','Canceled')
        ], default='New', required=True, copy=False,string="State", readonly=True)
    property_type_id = fields.Many2one('estate.property.type', string="Property Type")
    buyer_id = fields.Many2one('res.partner', string="Buyer", readonly=True)
    salesperson_id = fields.Many2one('res.users', string="Salesperson")
    tag_ids = fields.Many2many('estate.property.tags', string="Tags")
    offer_ids = fields.One2many('estate.property.offer','property_id', string="Offers")
    total_area = fields.Float(string="Total Area (sqm)", compute='_compute_total_area')
    best_price = fields.Float(string="Best Price", compute='_compute_best_price')

    _sql_constraints= [
        ('strictly_expected_price', 'CHECK(expected_price > 0)', 'A property expected price must be greater than 0'),
        ('selling_price_positive', 'CHECK(selling_price >= 0)', 'A property selling price must be positive')
    ]

    @api.depends('living_area', 'garden_area')
    def _compute_total_area(self):
        for record in self:
            record.total_area = record.living_area + record.garden_area

    @api.depends('offer_ids.price')
    def _compute_best_price(self):
        for record in self:
            record.best_price = max(record.offer_ids.mapped('price'),default=0.0)  

    @api.onchange('garden')
    def _onchange_garden(self):
        if self.garden:
            self.garden_area=10
            self.garden_orientation= 'North'
        else:
            self.garden_area=0
            self.garden_orientation=False  

    def action_cancel(self):
        for record in self:
            if record.state == 'Sold':
                raise UserError("cannot cancel a property that is already sold.")
            else:   
                record.state = 'Canceled'

    def action_set_sold(self):
        for record in self:
            if record.state == 'Canceled':
                raise UserError("Cannot set as sold a property that is canceled")
            else:
                record.state = 'Sold'  

    @api.constrains('expected_price','selling_price')
    def _check_selling_price(self):
        for record in self:
            if not float_is_zero(record.selling_price, precision_digits=2) and not float_is_zero(record.expected_price, precision_digits=2):
                min_selling_price = record.expected_price * 0.9
                if float_compare(record.selling_price, min_selling_price, precision_digits=2) == -1:
                    raise ValidationError("Selling price cannot be lower than 90% of the expected price")


class EstatePropertyType(models.Model):
    _name = "estate.property.type"
    _description = "Real Estate Property Type"

    name = fields.Char(string="name", required=True)

    _sql_constraints =[('Property_type_uniqe','UNIQUE(name)','Type name has been used, try another type name'),]

class EstatePropertyTags(models.Model):
    _name = "estate.property.tags"
    _description = "Property Tags"

    name = fields.Char(string="name", required=True)

    _sql_constraints =[('Property_tag_uniqe','UNIQUE(name)','Tag name has been used, try another tag name'),]


class EstatePropertyOffer(models.Model):
    _name = "estate.property.offer"
    _description = "Property Offer"

    price = fields.Float(string="Price", required=True)
    status = fields.Selection([
        ("Accepted", "Accepted"),
        ("Refused", "Refused")
    ], string="Status",copy=False)
    partner_id = fields.Many2one('res.partner', string="Partner", required=True)
    property_id = fields.Many2one('estate.property', string="Property")
    validity = fields.Integer(string="Validity", default=7)
    create_date = fields.Datetime(string="Create Date", default=fields.Datetime.now(), readonly=True)
    date_deadline = fields.Date(string="Date deadline", compute='_compute_date_deadline', inverse='_inverse_date_deadline')

    _sql_constraints = [('strictly_offer_price','CHECK(price > 0)','An offer price must be greater than 0')]

    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for record in self:
            if record.create_date and record.validity:
                create_date = datetime.combine(record.create_date, datetime.min.time())
                record.date_deadline = create_date.date() + timedelta(days=record.validity)

    @api.onchange('validity')
    def _onchange_validity(self):
        if self.create_date and self.validity:
            create_date = datetime.combine(self.create_date, datetime.min.time())
            self.date_deadline = create_date.date() + timedelta(days=self.validity)

    def _inverse_date_deadline(self):
        for record in self:
            if record.create_date and record.date_deadline:
                create_date = datetime.combine(record.create_date, datetime.min.time())
                record.validity = (record.date_deadline - create_date.date()).days

    @api.onchange('date_deadline')
    def _onchange_date_deadline(self):
        if self.create_date and self.date_deadline:
            create_date = datetime.combine(self.create_date, datetime.min.time())
            self.validity = (self.date_deadline - create_date.date()).days

    def action_accept(self):
        for record in self:
            if record.status == 'Accepted':
                raise UserError("This offer has already been accepted.")
            elif record.status == 'Refused':
                raise UserError("This offer has been refused.")
            else:
                property = record.property_id  # Dapatkan properti yang terkait dengan penawaran
                property.action_set_sold()  # Menetapkan properti sebagai "sold"
                property.buyer_id = record.partner_id
                property.selling_price = record.price
                record.status = 'Accepted'

    def action_refuse(self):
        for record in self:
            record.status = 'Refused'