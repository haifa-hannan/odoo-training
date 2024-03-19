from datetime import timedelta, datetime
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

class EstateProperty(models.Model):
    _name = "estate.property"
    _description = "Real Estate Property"
    _order = "id desc"

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
    salesperson_id = fields.Many2one('res.users', string="Salesperson", default=lambda self: self.env.user)
    tag_ids = fields.Many2many('estate.property.tags', string="Tags", widget="many2many_tags", options='{"color_field": "color"}')
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
                
    def unlink(self):
        for record in self:
            if record.state not in ['New', 'Canceled']:
                raise ValidationError("You can only delete properties with state 'New' or 'Canceled'.")
        return super(EstateProperty, self).unlink()

class EstatePropertyOffer(models.Model):
    _name = "estate.property.offer"
    _description = "Property Offer"
    _order = "price desc"

    price = fields.Float(string="Price", required=True)
    status = fields.Selection([
        ("Accepted", "Accepted"),
        ("Refused", "Refused")
    ], string="Status",copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', string="Partner", required=True)
    property_id = fields.Many2one('estate.property', string="Property")
    validity = fields.Integer(string="Validity", default=7)
    create_date = fields.Datetime(string="Create Date", default=fields.Datetime.now(), readonly=True)
    date_deadline = fields.Date(string="Date deadline", compute='_compute_date_deadline', inverse='_inverse_date_deadline')
    property_type_id = fields.Many2one(
        "estate.property.type", related="property_id.property_type_id", string="Property Type", store=True
    )

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
                property.state = 'Offer Accepted'
                property.buyer_id = record.partner_id
                property.selling_price = record.price
                record.status = 'Accepted'

    def action_refuse(self):
        for record in self:
            record.status = 'Refused'

    @api.model
    def create(self, vals):
        if vals.get("property_id") and vals.get("price"):
            prop = self.env["estate.property"].browse(vals["property_id"])
            # We check if the offer is higher than the existing offers
            if prop.offer_ids:
                max_offer = max(prop.mapped("offer_ids.price"))
                if float_compare(vals["price"], max_offer, precision_rounding=0.01) <= 0:
                    raise UserError("The offer must be higher than %.2f" % max_offer)
            prop.state = "Offer Received"
        return super().create(vals)

class EstatePropertyType(models.Model):
    _name = "estate.property.type"
    _description = "Real Estate Property Type"
    _order = "name"

    name = fields.Char(string="name", required=True)
    property_ids = fields.One2many('estate.property', 'property_type_id', string="Properties")
    sequence = fields.Integer('Sequence', default=1)
    offer_count = fields.Integer(string="Offers Count", compute="_compute_offer")
    offer_ids = fields.Many2many("estate.property.offer", string="Offers", compute="_compute_offer")

    _sql_constraints =[('Property_type_uniqe','UNIQUE(name)','Type name has been used, try another type name'),]

    def _compute_offer(self):
        # This solution is quite complex. It is likely that the trainee would have done a search in
        # a loop.
        data = self.env["estate.property.offer"].read_group(
            [("property_id.state", "!=", "canceled"), ("property_type_id", "!=", False)],
            ["ids:array_agg(id)", "property_type_id"],
            ["property_type_id"],
        )
        mapped_count = {d["property_type_id"][0]: d["property_type_id_count"] for d in data}
        mapped_ids = {d["property_type_id"][0]: d["ids"] for d in data}
        for prop_type in self:
            prop_type.offer_count = mapped_count.get(prop_type.id, 0)
            prop_type.offer_ids = mapped_ids.get(prop_type.id, [])

class EstatePropertyTags(models.Model):
    _name = "estate.property.tags"
    _description = "Property Tags"
    _order = "name"

    name = fields.Char(string="name", required=True)
    color = fields.Integer(string='Color')

    _sql_constraints =[('Property_tag_uniqe','UNIQUE(name)','Tag name has been used, try another tag name'),]

class ResUser(models.Model):
    _inherit = "res.users"

    property_ids = fields.One2many("estate.property", "salesperson_id", string="Properties", domain=[("state", "in", ('New', 'Over Received'))])