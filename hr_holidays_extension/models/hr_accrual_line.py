'''
Created on Aug 24, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields

class AccrualLine(models.Model):

    _name = 'hr.accrual.line'
    _description = 'Accrual Line'
    _rec_name = 'date'

    date = fields.Date('Date', required=True, default = fields.Date.today)
    accrual_id = fields.Many2one('hr.accrual', 'Accrual', required=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    amount = fields.Float('Amount', required=True)
