from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import json
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

TICKETS_FILE = 'tickets.json'

def load_tickets():
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_tickets(tickets):
    with open(TICKETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tickets, f, indent=2, ensure_ascii=False)

def get_next_ticket_id():
    tickets = load_tickets()
    if not tickets:
        return 1
    return max(t['id'] for t in tickets) + 1

SUDOKU_PUZZLE = [
    [1, 0, 0, 4],
    [0, 4, 1, 0],
    [2, 0, 0, 1],
    [0, 1, 2, 0]
]

SUDOKU_SOLUTION = [
    [1, 2, 3, 4],
    [3, 4, 1, 2],
    [2, 3, 4, 1],
    [4, 1, 2, 3]
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_ticket', methods=['GET', 'POST'])
def new_ticket():
    if request.method == 'POST':
        ticket_data = {
            'id': get_next_ticket_id(),
            'title': request.form.get('title', ''),
            'description': request.form.get('description', ''),
            'impact': request.form.get('impact', ''),
            'priority': request.form.get('priority', 'standard'),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        session['pending_ticket'] = ticket_data
        
        if ticket_data['priority'] == 'urgent':
            session['attempts'] = 3
            session['start_time'] = datetime.now().isoformat()
            return redirect(url_for('sudoku_challenge'))
        else:
            tickets = load_tickets()
            ticket_data['status'] = 'standard'
            tickets.append(ticket_data)
            save_tickets(tickets)
            return redirect(url_for('ticket_success', ticket_id=ticket_data['id']))
    
    return render_template('new_ticket.html')

@app.route('/sudoku', methods=['GET', 'POST'])
def sudoku_challenge():
    if 'pending_ticket' not in session:
        return redirect(url_for('new_ticket'))
    
    if request.method == 'POST':
        user_solution = []
        for i in range(4):
            row = []
            for j in range(4):
                val = request.form.get(f'cell_{i}_{j}', '0')
                row.append(int(val) if val.isdigit() else 0)
            user_solution.append(row)
        
        if user_solution == SUDOKU_SOLUTION:
            ticket_data = session['pending_ticket']
            ticket_data['status'] = 'urgent_validated'
            
            tickets = load_tickets()
            tickets.append(ticket_data)
            save_tickets(tickets)
            
            start_time = datetime.fromisoformat(session['start_time'])
            elapsed = (datetime.now() - start_time).total_seconds()
            
            session.pop('pending_ticket', None)
            session.pop('attempts', None)
            session.pop('start_time', None)
            
            return render_template('challenge_success.html', 
                                 elapsed=int(elapsed), 
                                 ticket_id=ticket_data['id'])
        else:
            session['attempts'] = session.get('attempts', 3) - 1
            
            if session['attempts'] <= 0:
                ticket_data = session['pending_ticket']
                ticket_data['status'] = 'downgraded_to_standard'
                ticket_data['priority'] = 'standard'
                
                tickets = load_tickets()
                tickets.append(ticket_data)
                save_tickets(tickets)
                
                session.pop('pending_ticket', None)
                session.pop('attempts', None)
                session.pop('start_time', None)
                
                return render_template('challenge_failed.html', 
                                     ticket_id=ticket_data['id'])
            
            return render_template('sudoku.html', 
                                 puzzle=SUDOKU_PUZZLE,
                                 attempts=session['attempts'],
                                 error="Solution incorrecte. Réessayez !")
    
    return render_template('sudoku.html', 
                         puzzle=SUDOKU_PUZZLE,
                         attempts=session.get('attempts', 3))

@app.route('/ticket/<int:ticket_id>')
def ticket_success(ticket_id):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['id'] == ticket_id), None)
    
    if not ticket:
        return redirect(url_for('index'))
    
    return render_template('ticket_success.html', ticket=ticket)

@app.route('/queue')
def queue():
    tickets = load_tickets()
    
    urgent_tickets = [t for t in tickets if t.get('status') == 'urgent_validated']
    standard_tickets = [t for t in tickets if t.get('status') in ['pending', 'standard', 'downgraded_to_standard']]
    
    return render_template('queue.html', 
                         urgent_tickets=urgent_tickets,
                         standard_tickets=standard_tickets)

@app.route('/stats')
def stats():
    tickets = load_tickets()
    
    total = len(tickets)
    urgent_validated = len([t for t in tickets if t.get('status') == 'urgent_validated'])
    downgraded = len([t for t in tickets if t.get('status') == 'downgraded_to_standard'])
    standard = len([t for t in tickets if t.get('status') in ['pending', 'standard']])
    
    stats_data = {
        'total': total,
        'urgent_validated': urgent_validated,
        'downgraded': downgraded,
        'standard': standard,
        'urgent_rate': round((urgent_validated / total * 100) if total > 0 else 0, 1),
        'success_rate': round((urgent_validated / (urgent_validated + downgraded) * 100) if (urgent_validated + downgraded) > 0 else 0, 1)
    }
    
    return render_template('stats.html', stats=stats_data)

if __name__ == '__main__':
    app.run(debug=True)