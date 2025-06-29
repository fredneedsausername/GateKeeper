import os
from psycopg_pool import ConnectionPool
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps 
from datetime import datetime, timedelta
import jwt
from dotenv import load_dotenv
from waitress import serve
from fredcrash import enable_crash_logging

load_dotenv()

app = Flask(__name__)

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DAYS = 365

FRONTEND_URL = os.getenv('FRONTEND_URL')
if not FRONTEND_URL:
    raise Exception("FRONTEND_URL environment variable needed")

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

pool = ConnectionPool(
    DATABASE_URL,
    min_size=2,
    max_size=20,
    open=True,
    timeout=30
)

def get_db():
    """Get database connection from pool"""
    return pool.connection()

def auth_required(f):
    """Decorator to require JWT authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'detail': 'Authorization header missing', 'status_code': 401}), 401
        
        if not token.startswith('Bearer '):
            return jsonify({'detail': 'Invalid authorization header format', 'status_code': 401}), 401
        
        token = token[7:]  # Remove 'Bearer ' prefix
        
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'detail': 'Token has expired', 'status_code': 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({'detail': 'Invalid token', 'status_code': 401}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({'detail': str(e), 'status_code': 500}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'detail': 'Username and password required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, username, password FROM users WHERE username = %s', (username,))
            user = cur.fetchone()
            
            if not user or user[2] != password:
                return jsonify({'detail': 'Invalid credentials', 'status_code': 401}), 401
            
            # Generate JWT token
            payload = {
                'user_id': user[0],
                'username': user[1],
                'exp': datetime.now() + timedelta(days=JWT_EXPIRATION_DAYS),
                'iat': datetime.now()
            }
            
            token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            
            return jsonify({'access_token': token}), 200

@app.route('/api/auth/me', methods=['GET'])
@auth_required
def get_current_user():
    return jsonify({
        'id': request.current_user['user_id'],
        'username': request.current_user['username']
    }), 200

@app.route('/api/crew-members', methods=['GET'])
@auth_required
def get_crew_members():
    ship_name = request.args.get('ship_name', '')
    crew_member_name = request.args.get('crew_member_name', '')
    role_name = request.args.get('role_name', '')
    skip = int(request.args.get('skip', 0))
    limit = min(int(request.args.get('limit', 50)), 100)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # Build query with filters
            query = """
                SELECT cm.id, cm.name, cm.role_id, cm.ship_id, cm.tag_id,
                       r.role_name, s.name as ship_name, 
                       t.id as tag_id, t.name as tag_name, t.remaining_battery
                FROM crew_member cm
                LEFT JOIN crew_member_roles r ON cm.role_id = r.id
                LEFT JOIN ship s ON cm.ship_id = s.id
                LEFT JOIN tag t ON cm.tag_id = t.id
                WHERE 1=1
            """
            params = []
            
            if ship_name:
                query += " AND LOWER(s.name) LIKE LOWER(%s)"
                params.append(f'%{ship_name}%')
            
            if crew_member_name:
                query += " AND LOWER(cm.name) LIKE LOWER(%s)"
                params.append(f'%{crew_member_name}%')
            
            if role_name:
                query += " AND LOWER(r.role_name) LIKE LOWER(%s)"
                params.append(f'%{role_name}%')

            # Count total
            count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY cm.name ASC LIMIT %s OFFSET %s"
            params.extend([limit, skip])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                item = {
                    'id': row[0],
                    'name': row[1],
                    'role': {
                        'id': row[2],
                        'role_name': row[5]
                    } if row[2] else None,
                    'ship': {
                        'id': row[3],
                        'name': row[6]
                    } if row[3] else None,
                    'tag': {
                        'id': row[7],
                        'name': row[8],
                        'remaining_battery': row[9]
                    } if row[7] else None
                }
                items.append(item)
            
            return jsonify({
                'items': items,
                'total': total
            }), 200

@app.route('/api/crew-members/<int:id>', methods=['GET'])
@auth_required
def get_crew_member(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.name, cm.role_id, cm.ship_id, cm.tag_id,
                       r.id as role_id, r.role_name, 
                       s.id as ship_id, s.name as ship_name,
                       t.id as tag_id, t.name as tag_name, t.remaining_battery, t.packet_counter
                FROM crew_member cm
                LEFT JOIN crew_member_roles r ON cm.role_id = r.id
                LEFT JOIN ship s ON cm.ship_id = s.id
                LEFT JOIN tag t ON cm.tag_id = t.id
                WHERE cm.id = %s
            """, (id,))
            
            row = cur.fetchone()
            if not row:
                return jsonify({'detail': 'Crew member not found', 'status_code': 404}), 404
            
            return jsonify({
                'id': row[0],
                'name': row[1],
                'role_id': row[2],
                'ship_id': row[3],
                'tag_id': row[4],
                'role': {
                    'id': row[5],
                    'role_name': row[6]
                } if row[5] else None,
                'ship': {
                    'id': row[7],
                    'name': row[8]
                } if row[7] else None,
                'tag': {
                    'id': row[9],
                    'name': row[10],
                    'remaining_battery': row[11],
                    'packet_counter': row[12]
                } if row[9] else None
            }), 200

@app.route('/api/crew-members', methods=['POST'])
@auth_required
def create_crew_member():
    data = request.get_json()
    name = data.get('name')
    role_id = data.get('role_id')
    ship_id = data.get('ship_id')
    tag_id = data.get('tag_id')
    
    if not name or not role_id or not ship_id:
        return jsonify({'detail': 'Name, role_id and ship_id are required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crew_member (name, role_id, ship_id, tag_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (name, role_id, ship_id, tag_id))
            
            new_id = cur.fetchone()[0]
            conn.commit()
            
    return get_crew_member(new_id)

@app.route('/api/crew-members/<int:id>', methods=['PUT'])
@auth_required
def update_crew_member(id):
    data = request.get_json()
    name = data.get('name')
    role_id = data.get('role_id')
    ship_id = data.get('ship_id')
    tag_id = data.get('tag_id')
    
    if not name or not role_id or not ship_id:
        return jsonify({'detail': 'Name, role_id and ship_id are required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE crew_member 
                SET name = %s, role_id = %s, ship_id = %s, tag_id = %s
                WHERE id = %s
            """, (name, role_id, ship_id, tag_id, id))
            
            if cur.rowcount == 0:
                return jsonify({'detail': 'Crew member not found', 'status_code': 404}), 404
            
            conn.commit()
            
    return get_crew_member(id)

@app.route('/api/crew-members/<int:id>', methods=['DELETE'])
@auth_required
def delete_crew_member(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM crew_member WHERE id = %s', (id,))
            conn.commit()
    
    return '', 204

@app.route('/api/ships', methods=['GET'])
@auth_required
def get_ships():
    name = request.args.get('name', '')
    skip = int(request.args.get('skip', 0))
    limit = min(int(request.args.get('limit', 50)), 100)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            query = "SELECT id, name FROM ship WHERE 1=1"
            params = []
            
            if name:
                query += " AND LOWER(name) LIKE LOWER(%s)"
                params.append(f'%{name}%')
            
            # Count total
            count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY name ASC LIMIT %s OFFSET %s"
            params.extend([limit, skip])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            items = [{'id': row[0], 'name': row[1]} for row in rows]
            
            return jsonify({
                'items': items,
                'total': total
            }), 200

@app.route('/api/ships/<int:id>', methods=['GET'])
@auth_required
def get_ship(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name FROM ship WHERE id = %s', (id,))
            row = cur.fetchone()
            
            if not row:
                return jsonify({'detail': 'Ship not found', 'status_code': 404}), 404
            
            return jsonify({'id': row[0], 'name': row[1]}), 200

@app.route('/api/ships', methods=['POST'])
@auth_required
def create_ship():
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'detail': 'Name is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO ship (name) VALUES (%s) RETURNING id', (name,))
            new_id = cur.fetchone()[0]
            conn.commit()
            
    return get_ship(new_id)

@app.route('/api/ships/<int:id>', methods=['PUT'])
@auth_required
def update_ship(id):
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'detail': 'Name is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE ship SET name = %s WHERE id = %s', (name, id))
            if cur.rowcount == 0:
                return jsonify({'detail': 'Ship not found', 'status_code': 404}), 404
            conn.commit()
            
    return get_ship(id)

@app.route('/api/ships/<int:id>', methods=['DELETE'])
@auth_required
def delete_ship(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM ship WHERE id = %s', (id,))
            conn.commit()
    
    return '', 204

# Tags endpoints
@app.route('/api/tags', methods=['GET'])
@auth_required
def get_tags():
    assigned = request.args.get('assigned')
    vacant = request.args.get('vacant')
    skip = int(request.args.get('skip', 0))
    limit = min(int(request.args.get('limit', 50)), 100)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT t.id, t.name, t.remaining_battery, t.packet_counter,
                       cm.id as cm_id, cm.name as cm_name
                FROM tag t
                LEFT JOIN crew_member cm ON t.id = cm.tag_id
                WHERE 1=1
            """
            params = []
            
            if assigned == 'true':
                query += " AND cm.id IS NOT NULL"
            elif vacant == 'true':
                query += " AND cm.id IS NULL"
            
            # Count total
            count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY t.remaining_battery ASC LIMIT %s OFFSET %s"
            params.extend([limit, skip])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                item = {
                    'id': row[0],
                    'name': row[1],
                    'remaining_battery': row[2],
                    'packet_counter': row[3],
                    'crew_member': {
                        'id': row[4],
                        'name': row[5]
                    } if row[4] else None
                }
                items.append(item)
            
            return jsonify({
                'items': items,
                'total': total
            }), 200

@app.route('/api/tags/<int:id>', methods=['GET'])
@auth_required
def get_tag(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.name, t.remaining_battery, t.packet_counter,
                       cm.id as cm_id, cm.name as cm_name
                FROM tag t
                LEFT JOIN crew_member cm ON t.id = cm.tag_id
                WHERE t.id = %s
            """, (id,))
            
            row = cur.fetchone()
            if not row:
                return jsonify({'detail': 'Tag not found', 'status_code': 404}), 404
            
            return jsonify({
                'id': row[0],
                'name': row[1],
                'remaining_battery': row[2],
                'packet_counter': row[3],
                'crew_member': {
                    'id': row[4],
                    'name': row[5]
                } if row[4] else None
            }), 200

@app.route('/api/tags/search', methods=['GET'])
@auth_required
def search_tags():
    name = request.args.get('name')
    
    if not name:
        return jsonify({'detail': 'Name parameter is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, remaining_battery
                FROM tag
                WHERE name = %s
            """, (name,))
            
            rows = cur.fetchall()
            tags = [{'id': row[0], 'name': row[1], 'remaining_battery': row[2]} for row in rows]
            
            return jsonify(tags), 200

@app.route('/api/tags', methods=['POST'])
@auth_required
def create_tag():
    data = request.get_json()
    name = data.get('name')
    crew_member_id = data.get('crew_member_id')
    
    if not name:
        return jsonify({'detail': 'Name is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # Create tag
            cur.execute("""
                INSERT INTO tag (name, remaining_battery, packet_counter)
                VALUES (%s, 100.0, 0)
                RETURNING id
            """, (name,))
            
            new_id = cur.fetchone()[0]
            
            # Assign to crew member if specified
            if crew_member_id:
                cur.execute("""
                    UPDATE crew_member SET tag_id = %s WHERE id = %s
                """, (new_id, crew_member_id))
            
            conn.commit()
            
    return get_tag(new_id)

@app.route('/api/tags/<int:id>', methods=['PUT'])
@auth_required
def update_tag(id):
    data = request.get_json()
    name = data.get('name')
    crew_member_id = data.get('crew_member_id')
    
    if not name:
        return jsonify({'detail': 'Name is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # Update tag name
            cur.execute('UPDATE tag SET name = %s WHERE id = %s', (name, id))
            if cur.rowcount == 0:
                return jsonify({'detail': 'Tag not found', 'status_code': 404}), 404
            
            # Unassign from any current crew member
            cur.execute('UPDATE crew_member SET tag_id = NULL WHERE tag_id = %s', (id,))
            
            # Assign to new crew member if specified
            if crew_member_id:
                cur.execute('UPDATE crew_member SET tag_id = %s WHERE id = %s', (id, crew_member_id))
            
            conn.commit()
            
    return get_tag(id)

@app.route('/api/tags/<int:id>', methods=['DELETE'])
@auth_required
def delete_tag(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tag WHERE id = %s', (id,))
            conn.commit()
    
    return '', 204

@app.route('/api/entries', methods=['GET'])
@auth_required
def get_entries():
    start_timestamp = request.args.get('start_timestamp')
    end_timestamp = request.args.get('end_timestamp')
    shipyard_name = request.args.get('shipyard_name', '')
    tag_name = request.args.get('tag_name', '')
    skip = int(request.args.get('skip', 0))
    limit = min(int(request.args.get('limit', 50)), 100)
    
    # Default to last 24 hours if not specified
    if not end_timestamp:
        end_timestamp = datetime.now().isoformat()
    if not start_timestamp:
        start_dt = datetime.fromisoformat(end_timestamp.replace('Z', '')) - timedelta(hours=24)
        start_timestamp = start_dt.isoformat()
    
    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT ute.id, ute.tag_id, ute.shipyard_id, ute.advertisement_timestamp, ute.is_entering,
                       t.name as tag_name, t.remaining_battery,
                       s.name as shipyard_name
                FROM unassigned_tag_entry ute
                JOIN tag t ON ute.tag_id = t.id
                JOIN shipyard s ON ute.shipyard_id = s.id
                WHERE advertisement_timestamp BETWEEN %s AND %s
            """
            params = [start_timestamp, end_timestamp]
            
            if shipyard_name:
                query += " AND LOWER(s.name) LIKE LOWER(%s)"
                params.append(f'%{shipyard_name}%')
            
            if tag_name:
                query += " AND t.name = %s"
                params.append(tag_name)
            
            # Count total
            count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY t.remaining_battery ASC LIMIT %s OFFSET %s"
            params.extend([limit, skip])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                item = {
                    'id': row[0],
                    'tag': {
                        'id': row[1],
                        'name': row[5],
                        'remaining_battery': row[6]
                    },
                    'shipyard': {
                        'id': row[2],
                        'name': row[7]
                    },
                    'advertisement_timestamp': row[3].isoformat(),
                    'is_entering': row[4]
                }
                items.append(item)
            
            return jsonify({
                'items': items,
                'total': total
            }), 200

@app.route('/api/entries/<int:id>', methods=['DELETE'])
@auth_required
def delete_entry(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM unassigned_tag_entry WHERE id = %s', (id,))
            conn.commit()
    
    return '', 204

@app.route('/api/logs', methods=['GET'])
@auth_required
def get_logs():
    start_timestamp = request.args.get('start_timestamp')
    end_timestamp = request.args.get('end_timestamp')
    shipyard_name = request.args.get('shipyard_name', '')
    ship_name = request.args.get('ship_name', '')
    crew_member_name = request.args.get('crew_member_name', '')
    skip = int(request.args.get('skip', 0))
    limit = min(int(request.args.get('limit', 50)), 100)
    
    # Default to last 24 hours if not specified
    if not end_timestamp:
        end_timestamp = datetime.now().isoformat()
    if not start_timestamp:
        start_dt = datetime.fromisoformat(end_timestamp.replace('Z', '')) - timedelta(hours=24)
        start_timestamp = start_dt.isoformat()
    
    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT pl.id, pl.crew_member_id, pl.shipyard_id, 
                       pl.entry_timestamp, pl.leave_timestamp,
                       cm.name as cm_name, cm.role_id, cm.ship_id, cm.tag_id,
                       r.role_name, s.name as ship_name, sh.name as shipyard_name,
                       t.name as tag_name, t.remaining_battery
                FROM permanence_log pl
                JOIN crew_member cm ON pl.crew_member_id = cm.id
                LEFT JOIN crew_member_roles r ON cm.role_id = r.id
                LEFT JOIN ship s ON cm.ship_id = s.id
                JOIN shipyard sh ON pl.shipyard_id = sh.id
                LEFT JOIN tag t ON cm.tag_id = t.id
                WHERE (
                    (pl.entry_timestamp IS NOT NULL AND pl.entry_timestamp BETWEEN %s AND %s) OR
                    (pl.leave_timestamp IS NOT NULL AND pl.leave_timestamp BETWEEN %s AND %s) OR
                    (pl.entry_timestamp <= %s AND (pl.leave_timestamp >= %s OR pl.leave_timestamp IS NULL))
                )
            """
            params = [start_timestamp, end_timestamp, start_timestamp, end_timestamp, end_timestamp, start_timestamp]
            
            if shipyard_name:
                query += " AND LOWER(sh.name) LIKE LOWER(%s)"
                params.append(f'%{shipyard_name}%')
            
            if ship_name:
                query += " AND LOWER(s.name) LIKE LOWER(%s)"
                params.append(f'%{ship_name}%')
            
            if crew_member_name:
                query += " AND LOWER(cm.name) LIKE LOWER(%s)"
                params.append(f'%{crew_member_name}%')
            
            # Count total
            count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY cm.name ASC LIMIT %s OFFSET %s"
            params.extend([limit, skip])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                item = {
                    'id': row[0],
                    'crew_member': {
                        'id': row[1],
                        'name': row[5],
                        'role': {
                            'id': row[6],
                            'role_name': row[9]
                        } if row[6] else None,
                        'ship': {
                            'id': row[7],
                            'name': row[10]
                        } if row[7] else None,
                        'tag': {
                            'id': row[8],
                            'name': row[12],
                            'remaining_battery': row[13]
                        } if row[8] else None
                    },
                    'shipyard': {
                        'id': row[2],
                        'name': row[11]
                    },
                    'entry_timestamp': row[3].isoformat() if row[3] else None,
                    'leave_timestamp': row[4].isoformat() if row[4] else None
                }
                items.append(item)
            
            return jsonify({
                'items': items,
                'total': total
            }), 200

@app.route('/api/logs/<int:id>', methods=['GET'])
@auth_required
def get_log(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pl.id, pl.crew_member_id, pl.shipyard_id, 
                       pl.entry_timestamp, pl.leave_timestamp,
                       cm.name as cm_name, cm.role_id, cm.ship_id, cm.tag_id,
                       r.role_name, s.name as ship_name, sh.name as shipyard_name,
                       t.name as tag_name, t.remaining_battery
                FROM permanence_log pl
                JOIN crew_member cm ON pl.crew_member_id = cm.id
                LEFT JOIN crew_member_roles r ON cm.role_id = r.id
                LEFT JOIN ship s ON cm.ship_id = s.id
                JOIN shipyard sh ON pl.shipyard_id = sh.id
                LEFT JOIN tag t ON cm.tag_id = t.id
                WHERE pl.id = %s
            """, (id,))
            
            row = cur.fetchone()
            if not row:
                return jsonify({'detail': 'Log not found', 'status_code': 404}), 404
            
            return jsonify({
                'id': row[0],
                'crew_member_id': row[1],
                'shipyard_id': row[2],
                'entry_timestamp': row[3].isoformat() if row[3] else None,
                'leave_timestamp': row[4].isoformat() if row[4] else None,
                'crew_member': {
                    'id': row[1],
                    'name': row[5],
                    'role': {
                        'id': row[6],
                        'role_name': row[9]
                    } if row[6] else None,
                    'ship': {
                        'id': row[7],
                        'name': row[10]
                    } if row[7] else None,
                    'tag': {
                        'id': row[8],
                        'name': row[12],
                        'remaining_battery': row[13]
                    } if row[8] else None
                },
                'shipyard': {
                    'id': row[2],
                    'name': row[11]
                }
            }), 200

@app.route('/api/logs', methods=['POST'])
@auth_required
def create_log():
    data = request.get_json()
    crew_member_id = data.get('crew_member_id')
    shipyard_id = data.get('shipyard_id')
    entry_timestamp = data.get('entry_timestamp')
    leave_timestamp = data.get('leave_timestamp')
    
    if not crew_member_id or not shipyard_id:
        return jsonify({'detail': 'crew_member_id and shipyard_id are required', 'status_code': 400}), 400
    
    if not entry_timestamp and not leave_timestamp:
        return jsonify({'detail': 'At least one of entry_timestamp or leave_timestamp is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO permanence_log (crew_member_id, shipyard_id, entry_timestamp, leave_timestamp)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (crew_member_id, shipyard_id, entry_timestamp, leave_timestamp))
            
            new_id = cur.fetchone()[0]
            conn.commit()
            
    return get_log(new_id)

@app.route('/api/logs/<int:id>', methods=['PUT'])
@auth_required
def update_log(id):
    data = request.get_json()
    crew_member_id = data.get('crew_member_id')
    entry_timestamp = data.get('entry_timestamp')
    leave_timestamp = data.get('leave_timestamp')
    
    if not crew_member_id:
        return jsonify({'detail': 'crew_member_id is required', 'status_code': 400}), 400
    
    if not entry_timestamp and not leave_timestamp:
        return jsonify({'detail': 'At least one of entry_timestamp or leave_timestamp is required', 'status_code': 400}), 400
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE permanence_log 
                SET crew_member_id = %s, entry_timestamp = %s, leave_timestamp = %s
                WHERE id = %s
            """, (crew_member_id, entry_timestamp, leave_timestamp, id))
            
            if cur.rowcount == 0:
                return jsonify({'detail': 'Log not found', 'status_code': 404}), 404
            
            conn.commit()
            
    return get_log(id)

@app.route('/api/logs/<int:id>', methods=['DELETE'])
@auth_required
def delete_log(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM permanence_log WHERE id = %s', (id,))
            conn.commit()
    
    return '', 204

@app.route('/api/advertisements', methods=['POST'])
@auth_required
def process_advertisement():
    """It is not yet known how the advertisements are structured, the endpoint will be implemented at a later time"""

@app.route('/api/roles', methods=['GET'])
@auth_required
def get_roles():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, role_name FROM crew_member_roles ORDER BY role_name')
            rows = cur.fetchall()
            roles = [{'id': row[0], 'role_name': row[1]} for row in rows]
            return jsonify(roles), 200

@app.route('/api/shipyards', methods=['GET'])
@auth_required
def get_shipyards():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name FROM shipyard ORDER BY name')
            rows = cur.fetchall()
            shipyards = [{'id': row[0], 'name': row[1]} for row in rows]
            return jsonify(shipyards), 200

@app.route('/api/activator-beacons', methods=['GET'])
@auth_required
def get_activator_beacons():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ab.id, ab.number, ab.shipyard_id, ab.is_first_when_entering,
                       s.name as shipyard_name
                FROM activator_beacon ab
                JOIN shipyard s ON ab.shipyard_id = s.id
                ORDER BY ab.number
            """)
            rows = cur.fetchall()
            beacons = []
            for row in rows:
                beacon = {
                    'id': row[0],
                    'number': row[1],
                    'shipyard': {
                        'id': row[2],
                        'name': row[4]
                    },
                    'is_first_when_entering': row[3]
                }
                beacons.append(beacon)
            return jsonify(beacons), 200

if __name__ == '__main__':
    
    enable_crash_logging("..")

    if (flask_port := int(os.getenv('FLASK_PORT'))) == None:
        raise Exception("FLASK_PORT environment variable needed")
    
    if (flask_env := os.getenv('FLASK_ENV')) == None:
        raise Exception("FLASK_ENV environment variable needed")
    
    if flask_env == 'production':
        serve(app, host='0.0.0.0', port=flask_port)

    elif flask_env == 'development':
        app.run(debug=True, host='127.0.0.1', port=5000)
    
    else:
        raise Exception(f"FLASK_ENV environment variable not recognized: {flask_env}")