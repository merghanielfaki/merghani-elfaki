'''
Created on Dec 18, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields

class HolidaysApproval(models.Model):
    _name = "hr.holidays.approval"
    _inherit = 'approval.config'
    
    sla_date_count = fields.Integer("SLA")