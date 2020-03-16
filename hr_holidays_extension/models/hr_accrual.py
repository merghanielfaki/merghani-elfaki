'''
Created on Aug 24, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api

class Accrual(models.Model):

    _name = 'hr.accrual'
    _description = 'Accrual'

    name = fields.Char('Name', size=128, required=True)
    holiday_status_id = fields.Many2one('hr.leave.type', 'Leave')
    line_ids = fields.One2many('hr.accrual.line', 'accrual_id', 'Accrual Lines', readonly=True)
    
    #@api.multi
    def get_balance(self, employee_id, date=None):
        date = date or fields.Date.today()
        cr = self._cr

        cr.execute('''SELECT SUM(amount) from hr_accrual_line \
                           WHERE accrual_id in %s AND employee_id=%s AND date <= %s''',
                   (self._ids, employee_id, date))
        
        res = cr.fetchone()
        
        return res and res[0]
