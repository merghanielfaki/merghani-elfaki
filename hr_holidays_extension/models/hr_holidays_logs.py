'''
Created on Dec 18, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields

class HolidayLog(models.Model):
    _name = 'hr.holidays.logs'
    _inherit = 'approval.log'
    
    record_id = fields.Many2one('hr.leave')