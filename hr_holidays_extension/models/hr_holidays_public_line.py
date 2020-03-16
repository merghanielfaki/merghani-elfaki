'''
Created on Aug 13, 2017

@author: Zuhair Hammadi
'''
from odoo import models, fields, api

class HolidaysPublicLine(models.Model):

    _name = 'hr.holidays.public.line'
    _description = 'Public Holidays Lines'
    _order = "date, name desc"

    name = fields.Char('Name', size=128, required=True)
    date = fields.Date('Date', required=True)
    holidays_id = fields.Many2one('hr.holidays.public', 'Holiday Calendar Year')
    variable = fields.Boolean('Date may change')
        
   #@api.multi
    def write(self, vals):
        dates = []
        if 'date' in vals:
            dates.append(vals['date'])
            dates.extend(self.mapped('date'))
        res= super(HolidaysPublicLine, self).write(vals)
        self._update_attendance(dates)            
        return res
        
    @api.model
    @api.returns('self', lambda value:value.id)
    def create(self, vals):
        self._update_attendance([vals['date']])
        return super(HolidaysPublicLine, self).create(vals)
    
   #@api.multi
    def unlink(self):
        dates = self.mapped('date')
        res= super(HolidaysPublicLine, self).unlink()
        self._update_attendance(dates)            
        return res
    
    @api.model
    def _update_attendance(self, dates):
        if not dates:
            return
        date_from = min(dates)
        date_to = max(dates)
        self.env['hr.attendance.date'].sudo().search([('date', '>=', date_from), ('date', '<=', date_to)])._compute()
