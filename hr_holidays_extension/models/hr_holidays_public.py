'''
Created on Aug 13, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from datetime import date

class HolidaysPublic(models.Model):

    _name = 'hr.holidays.public'
    _description = 'Public Holidays'
    _rec_name = 'year'
    _order = "year"

    year = fields.Char("calendar Year", required=True)
    line_ids = fields.One2many('hr.holidays.public.line', 'holidays_id', 'Holiday Dates')
    
    _sql_constraints = [
        ('year_unique', 'UNIQUE(year)', _('Duplicate year!')),
    ]
    
    @api.model
    def is_public_holiday(self, dt):
        if isinstance(dt, date):
            dt = fields.Date.to_string(dt)
        year = dt[:4]
        return bool(self.env['hr.holidays.public.line'].search([('date','=', dt), ('holidays_id.year','=', year)], count = True))
    
    @api.model
    def get_holidays_list(self, year):
        return self.env['hr.holidays.public.line'].search([('holidays_id.year','=', year)]).mapped('date')