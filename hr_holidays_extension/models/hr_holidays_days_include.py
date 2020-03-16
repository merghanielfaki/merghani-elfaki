'''
Created on Aug 13, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields

class HolidaysDaysInclude(models.Model):
    _name = 'hr.holidays.days_include'

    request_id = fields.Many2one("hr.leave", "Holiday Request")
    tdate = fields.Date('Trigger Date')
    date_type = fields.Selection([('e', 'Excluded'), ('i', 'Included')], string='Type')
    status = fields.Selection([('a', 'Approved'), ('n', 'Not Approved')], string='Status')
    employee_id = fields.Many2one('hr.employee', "Employee")
    