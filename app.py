from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import pyodbc
import os
from datetime import datetime
from openpyxl import load_workbook
import io

app = Flask(__name__)
# 使用环境变量或随机密钥（生产环境请使用环境变量）
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')

# ==================== 数据库连接配置 ====================
# ==================== 数据库连接配置 ====================
def get_db_connection():
    """获取数据库连接"""
    try:
        # 使用默认实例 + 正确的数据库名
        conn = pyodbc.connect(
            r'DRIVER={ODBC Driver 17 for SQL Server};'
            r'SERVER=.;'
            r'DATABASE=StudentManage;'
            r'Trusted_Connection=yes;'
        )
        return conn
    except Exception as e:
        print(f"默认实例连接失败: {e}")
        try:
            # 备用：使用 localhost
            conn = pyodbc.connect(
                r'DRIVER={ODBC Driver 17 for SQL Server};'
                r'SERVER=localhost;'
                r'DATABASE=StudentManage;'
                r'Trusted_Connection=yes;'
            )
            return conn
        except Exception as e2:
            print(f"localhost 连接也失败: {e2}")
            raise
# ==================== 权限装饰器 ====================
def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录！', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """角色权限验证装饰器
    roles: 1-学生, 2-教师, 3-管理员
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('请先登录！', 'warning')
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('权限不足！', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== 1. 登录/注册路由 ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面 - 支持学生、教师、管理员三表登录"""
    if request.method == 'POST':
        account = request.form.get('account')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        if not account or not password:
            flash('请输入账号和密码！', 'warning')
            return render_template('login.html')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 使用存储过程进行统一登录验证
            cursor.execute(
                "{CALL usp_UserLogin (?, ?)}",
                (account, password)
            )
            user = cursor.fetchone()
            
            if user:
                user_id = user[0]
                user_name = user[1]
                role = user[2]
                user_type = user[3]
                
                session['user_id'] = user_id
                session['username'] = user_name
                session['role'] = role
                session['login_time'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                if remember:
                    session.permanent = True
                
                role_names = {'Student': '学生', 'Teacher': '教师', 'Admin': '管理员'}
                flash(f'欢迎回来，{user_name}（{role_names.get(user_type, user_type)}）！', 'success')
                conn.close()
                return redirect(url_for('index'))
            else:
                flash('账号或密码错误！', 'error')
            
            conn.close()
            
        except Exception as e:
            flash('登录失败，请稍后重试！', 'error')
            print(f"登录错误: {e}")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """学生注册页面"""
    if request.method == 'POST':
        sno = request.form.get('sno')
        sname = request.form.get('sname')
        password = request.form.get('password')
        ssex = request.form.get('ssex')
        cid = request.form.get('cid')
        nation = request.form.get('nation')
        sbirthday = request.form.get('sbirthday')
        location = request.form.get('location')
        enrol = request.form.get('enrol')
        
        # 表单验证
        if not all([sno, sname, password]):
            flash('请填写所有必填项！', 'warning')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('密码长度不能少于6位！', 'warning')
            return render_template('register.html')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 检查学号是否已存在
            cursor.execute("SELECT Sno FROM Student WHERE Sno = ?", (sno,))
            if cursor.fetchone():
                flash('该学号已被注册！', 'error')
                conn.close()
                return render_template('register.html')
            
            # 插入新学生 - 使用实际的表结构
            # 注意：Sno=学号, UserAccount=登录账号(默认用学号), UserPwd=密码
            cursor.execute(
                """INSERT INTO Student (Sno, Sname, Ssex, Cid, Nation, Sbirthday, Location, Enrol, UserPwd, Role) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (sno, sname, ssex, cid, nation, sbirthday, location, enrol, password)
            )
            
            conn.commit()
            conn.close()
            
            flash('注册成功，请使用学号登录！', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('注册失败，请稍后重试！', 'error')
            print(f"注册错误: {e}")
            
    return render_template('register.html')

@app.route('/register_teacher', methods=['GET', 'POST'])
def register_teacher():
    """教师注册页面（需要管理员审核）"""
    if request.method == 'POST':
        tid = request.form.get('tid')
        tname = request.form.get('tname')
        password = request.form.get('password')
        did = request.form.get('did')
        
        # 表单验证
        if not all([tid, tname, password]):
            flash('请填写所有必填项！', 'warning')
            return render_template('register_teacher.html')
        
        if len(password) < 6:
            flash('密码长度不能少于6位！', 'warning')
            return render_template('register_teacher.html')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 检查教师编号是否已存在
            cursor.execute("SELECT Tid FROM Teacher WHERE Tid = ?", (tid,))
            if cursor.fetchone():
                flash('该教师编号已被注册！', 'error')
                conn.close()
                return render_template('register_teacher.html')
            
            # 插入新教师 - 默认未审核 (Status=0)
            cursor.execute(
                """INSERT INTO Teacher (Tid, Tname, Did, UserPwd, Status) 
                   VALUES (?, ?, ?, ?, 0)""",
                (tid, tname, did, password)
            )
            
            conn.commit()
            conn.close()
            
            flash('注册申请已提交，请等待管理员审核！', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('注册失败，请稍后重试！', 'error')
            print(f"教师注册错误: {e}")
            
    # 获取院系列表供选择
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Did, Dname FROM Department ORDER BY Did")
        departments = cursor.fetchall()
        conn.close()
    except:
        departments = []
            
    return render_template('register_teacher.html', departments=departments)

@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    flash('已安全退出！', 'success')
    return redirect(url_for('login'))

# ==================== 2. 首页路由 ====================
@app.route('/')
@app.route('/index')
@login_required
def index():
    """系统首页"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取院系统计信息
        dept_summary = []
        try:
            # 尝试调用存储过程
            cursor.execute("{CALL usp_GetDepartmentStudentCount}")
            rows = cursor.fetchall()
            for row in rows:
                dept_summary.append({
                    "院系编号": row[0],
                    "院系名称": row[1],
                    "学生总数": row[2]
                })
        except Exception as e:
            print(f"存储过程调用失败: {e}")
            # 备用查询
            try:
                cursor.execute("""
                    SELECT d.Did, d.Dname, COUNT(s.Sno) as student_count
                    FROM Department d
                    LEFT JOIN Major m ON d.Did = m.Did
                    LEFT JOIN Class c ON m.Mid = c.Mid
                    LEFT JOIN Student s ON c.Cid = s.Cid
                    GROUP BY d.Did, d.Dname
                """)
                rows = cursor.fetchall()
                for row in rows:
                    dept_summary.append({
                        "院系编号": row[0],
                        "院系名称": row[1],
                        "学生总数": row[2] or 0
                    })
            except Exception as e2:
                print(f"备用查询也失败: {e2}")
        
        conn.close()
        
        return render_template('index.html', 
                             dept_summary=dept_summary,
                             username=session.get('username'),
                             role=session.get('role'))
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"首页错误: {e}")
        return render_template('index.html', dept_summary=[])

# ==================== 3. 院系管理路由 ====================
@app.route('/dept', methods=['GET', 'POST'])
@login_required
def dept():
    """院系管理页面（仅管理员）"""
    if session.get('role') != 3:
        flash('权限不足！', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            did = request.form.get('did')
            dname = request.form.get('dname')
            
            if not all([did, dname]):
                flash('请填写完整的院系信息！', 'warning')
            else:
                try:
                    cursor.execute("INSERT INTO Department (Did, Dname) VALUES (?, ?)", (did, dname))
                    conn.commit()
                    flash('院系添加成功！', 'success')
                except Exception as e:
                    flash('院系添加失败，编号可能已存在！', 'error')
                    print(f"添加院系错误: {e}")
        
        elif action == 'delete':
            did = request.form.get('did')
            try:
                cursor.execute("DELETE FROM Department WHERE Did = ?", (did,))
                conn.commit()
                flash('院系删除成功！', 'success')
            except Exception as e:
                flash('院系删除失败，可能存在关联数据！', 'error')
                print(f"删除院系错误: {e}")
    
    # 获取所有院系
    try:
        cursor.execute("SELECT Did, Dname FROM Department ORDER BY Did")
        departments = cursor.fetchall()
    except:
        departments = []
    
    conn.close()
    
    return render_template('dept.html', departments=departments)

# ==================== 4. 成绩管理路由 ====================
@app.route('/score', methods=['GET', 'POST'])
@login_required
def score():
    """成绩管理页面（仅教师）"""
    if session.get('role') != 2:
        flash('权限不足！', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取当前教师所属院系
    user_id = session.get('user_id')
    teacher_dept = None
    cursor.execute("SELECT Did FROM Teacher WHERE Tid = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        teacher_dept = result[0]

    # 获取查询参数（GET请求）
    search_sno = request.args.get('search_sno', '').strip()
    search_cname = request.args.get('search_cname', '').strip()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            sno = request.form.get('sno')
            cno = request.form.get('cno')
            score_val = request.form.get('score')

            if not all([sno, cno, score_val]):
                flash('请填写完整的成绩信息！', 'warning')
            else:
                try:
                    # 教师只能为所在院系学生录入成绩
                    if teacher_dept:
                        cursor.execute("""
                            SELECT d.Did 
                            FROM Student s
                            JOIN Class c ON s.Cid = c.Cid
                            JOIN Major m ON c.Mid = m.Mid
                            WHERE s.Sno = ?
                        """, (sno,))
                        student_dept = cursor.fetchone()
                        if not student_dept or student_dept[0] != teacher_dept:
                            flash('您只能为所在院系的学生录入成绩！', 'error')
                            conn.close()
                            return redirect(url_for('score'))

                    cursor.execute(
                        "INSERT INTO Grade (Cno, Sno, Score) VALUES (?, ?, ?)",
                        (cno, sno, int(score_val))
                    )
                    conn.commit()
                    flash('成绩录入成功！', 'success')
                except Exception as e:
                    flash('成绩录入失败！', 'error')
                    print(f"录入成绩错误: {e}")

        elif action == 'delete':
            sno = request.form.get('sno')
            cno = request.form.get('cno')
            try:
                # 教师只能删除所在院系学生的成绩
                if teacher_dept:
                    cursor.execute("""
                        SELECT d.Did 
                        FROM Student s
                        JOIN Class c ON s.Cid = c.Cid
                        JOIN Major m ON c.Mid = m.Mid
                        WHERE s.Sno = ?
                    """, (sno,))
                    student_dept = cursor.fetchone()
                    if not student_dept or student_dept[0] != teacher_dept:
                        flash('您只能删除所在院系学生的成绩！', 'error')
                        conn.close()
                        return redirect(url_for('score'))

                cursor.execute("DELETE FROM Grade WHERE Sno = ? AND Cno = ?", (sno, cno))
                conn.commit()
                flash('成绩删除成功！', 'success')
            except Exception as e:
                flash('成绩删除失败！', 'error')
                print(f"删除成绩错误: {e}")
        elif action == 'import':
            # Excel批量导入成绩
            if 'file' not in request.files:
                flash('请选择要上传的文件！', 'warning')
            else:
                file = request.files['file']
                if file.filename == '':
                    flash('请选择要上传的文件！', 'warning')
                elif not file.filename.endswith(('.xlsx', '.xls')):
                    flash('请上传Excel文件（.xlsx或.xls格式）！', 'warning')
                else:
                    try:
                        # 读取Excel文件
                        wb = load_workbook(filename=io.BytesIO(file.read()))
                        ws = wb.active

                        success_count = 0
                        error_count = 0
                        error_msgs = []

                        # 从第2行开始读取（假设第1行是表头）
                        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                            if len(row) < 3:
                                continue

                            cno, sno, score_val = row[0], row[1], row[2]

                            # 数据验证
                            if not all([cno, sno, score_val]):
                                error_count += 1
                                error_msgs.append(f"第{row_idx}行：数据不完整")
                                continue

                            try:
                                score_num = int(score_val)
                                if score_num < 0 or score_num > 100:
                                    error_count += 1
                                    error_msgs.append(f"第{row_idx}行：分数{score_num}超出范围(0-100)")
                                    continue
                            except:
                                error_count += 1
                                error_msgs.append(f"第{row_idx}行：分数格式错误")
                                continue

                            # 插入数据库
                            try:
                                cursor.execute(
                                    "INSERT INTO Grade (Cno, Sno, Score) VALUES (?, ?, ?)",
                                    (str(cno), str(sno), score_num)
                                )
                                success_count += 1
                            except Exception as e:
                                error_count += 1
                                error_msgs.append(f"第{row_idx}行：{str(e)[:50]}")

                        conn.commit()

                        # 显示导入结果
                        if success_count > 0:
                            flash(f'成功导入 {success_count} 条成绩记录！', 'success')
                        if error_count > 0:
                            flash(f'导入失败 {error_count} 条，请检查数据格式', 'warning')
                            for msg in error_msgs[:5]:  # 只显示前5条错误
                                flash(msg, 'error')

                    except Exception as e:
                        flash(f'文件解析失败：{str(e)}', 'error')
                        print(f"Excel导入错误: {e}")

    # 获取成绩（使用B_Grade视图）- 支持查询筛选
    try:
        sql = """
            SELECT b.Sno, b.Sname, b.Cname, b.Score
            FROM B_Grade b
            JOIN Student s ON b.Sno = s.Sno
            JOIN Class cl ON s.Cid = cl.Cid
            JOIN Major m ON cl.Mid = m.Mid
            WHERE m.Did = ?
        """
        params = [teacher_dept]

        if search_sno:
            sql += " AND b.Sno LIKE ?"
            params.append(f"%{search_sno}%")

        if search_cname:
            sql += " AND b.Cname LIKE ?"
            params.append(f"%{search_cname}%")

        sql += " ORDER BY b.Sno, b.Cname"

        cursor.execute(sql, params)
        scores = cursor.fetchall()
    except Exception as e:
        print(f"查询成绩错误: {e}")
        scores = []

    conn.close()

    return render_template('score.html', scores=scores, teacher_dept=teacher_dept,
                         search_sno=search_sno, search_cname=search_cname)

# ==================== 5. 数据统计路由 ====================
@app.route('/stat')
@login_required
def stat():
    """学业预警统计页面（教师/管理员）"""
    if session.get('role') not in [2, 3]:
        flash('权限不足！', 'error')
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取当前用户的角色和院系信息
        user_role = session.get('role')
        user_id = session.get('user_id')
        teacher_dept = None

        # 如果是教师，获取其所属院系
        if user_role == 2:
            cursor.execute("SELECT Did FROM Teacher WHERE Tid = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                teacher_dept = result[0]

        # 获取课程列表（用于白色区域下拉筛选）
        try:
            cursor.execute("SELECT Cno, Cname FROM Course ORDER BY Cno")
            courses = cursor.fetchall()
            print(f"[DEBUG] stat: 课程列表={courses}")
        except Exception as e:
            print(f"[DEBUG] stat: 课程查询失败={e}")
            courses = []

        # 获取筛选参数（白色区域用）
        course_id = request.args.get('course_id', '').strip()

        # 获取不及格成绩（使用usp_GetFailedStudents存储过程）
        try:
            # 调用存储过程查询不及格学生
            if course_id:
                cursor.execute("EXEC usp_GetFailedStudents ?", (course_id,))
            else:
                cursor.execute("EXEC usp_GetFailedStudents ?", None)
            all_failed = cursor.fetchall()

            # 如果是教师，过滤本院系学生
            if user_role == 2 and teacher_dept:
                failed_scores = []
                for row in all_failed:
                    cursor.execute("""
                        SELECT 1 FROM Student s
                        JOIN Class cl ON s.Cid = cl.Cid
                        JOIN Major m ON cl.Mid = m.Mid
                        WHERE s.Sno = ? AND m.Did = ?
                    """, (row[0], teacher_dept))
                    if cursor.fetchone():
                        failed_scores.append(row)
            else:
                failed_scores = all_failed
        except Exception as e:
            print(f"查询预警数据错误: {e}")
            failed_scores = []

        # 统计信息
        stats = {
            'total_failed': len(failed_scores),
            'unique_students': len(set([s[0] for s in failed_scores])),
            'unique_courses': len(set([s[2] for s in failed_scores]))
        }

        conn.close()

        return render_template('stat.html', 
                             failed_scores=failed_scores,
                             stats=stats,
                             teacher_dept=teacher_dept,
                             courses=courses,
                             course_id=course_id)
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"统计页面错误: {e}")
        return render_template('stat.html', failed_scores=[], stats={}, courses=[], course_id='')

# ==================== 6. 管理员管理路由 ====================
@app.route('/admin/manage')
@login_required
@role_required(3)
def admin_manage():
    """管理员管理页面（仅初始管理员可创建其他管理员）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取待审核的教师列表
        cursor.execute("""
            SELECT t.Tid, t.Tname, d.Dname, t.Status 
            FROM Teacher t
            LEFT JOIN Department d ON t.Did = d.Did
            WHERE t.Status = 0 
            ORDER BY t.Tid
        """)
        pending_teachers = cursor.fetchall()

        # 获取已审核的教师列表
        cursor.execute("""
            SELECT t.Tid, t.Tname, d.Dname, t.Status 
            FROM Teacher t
            LEFT JOIN Department d ON t.Did = d.Did
            WHERE t.Status = 1 
            ORDER BY t.Tid
        """)
        approved_teachers = cursor.fetchall()
        
        # 获取所有管理员列表
        cursor.execute("""
            SELECT Aid, Aname 
            FROM SysAdmin 
            ORDER BY Aid
        """)
        admins = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin_manage.html',
                             pending_teachers=pending_teachers,
                             approved_teachers=approved_teachers,
                             admins=admins)
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"管理员管理错误: {e}")
        return render_template('admin_manage.html', 
                             pending_teachers=[], 
                             approved_teachers=[], 
                             admins=[])

@app.route('/admin/approve_teacher/<tid>')
@login_required
@role_required(3)
def approve_teacher(tid):
    """审核通过教师账号"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Teacher SET Status = 1 WHERE Tid = ?",
            (tid,)
        )
        conn.commit()
        conn.close()
        flash('教师账号审核通过！', 'success')
    except Exception as e:
        flash('审核失败！', 'error')
        print(f"审核教师错误: {e}")
    return redirect(url_for('admin_manage'))

@app.route('/admin/reject_teacher/<tid>')
@login_required
@role_required(3)
def reject_teacher(tid):
    """拒绝教师账号申请"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM Teacher WHERE Tid = ? AND Status = 0",
            (tid,)
        )
        conn.commit()
        conn.close()
        flash('已拒绝该教师申请！', 'success')
    except Exception as e:
        flash('操作失败！', 'error')
        print(f"拒绝教师错误: {e}")
    return redirect(url_for('admin_manage'))

@app.route('/admin/add_admin', methods=['POST'])
@login_required
@role_required(3)
def add_admin():
    """添加新管理员（仅初始管理员可操作）"""
    aid = request.form.get('aid')
    aname = request.form.get('aname')
    password = request.form.get('password')
    
    if not all([aid, aname, password]):
        flash('请填写所有必填项！', 'warning')
        return redirect(url_for('admin_manage'))
    
    if len(password) < 6:
        flash('密码长度不能少于6位！', 'warning')
        return redirect(url_for('admin_manage'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查管理员ID是否已存在
        cursor.execute("SELECT Aid FROM SysAdmin WHERE Aid = ?", (aid,))
        if cursor.fetchone():
            flash('该管理员ID已存在！', 'error')
            conn.close()
            return redirect(url_for('admin_manage'))
        
        # 插入新管理员
        cursor.execute(
            "INSERT INTO SysAdmin (Aid, Aname, UserPwd) VALUES (?, ?, ?)",
            (aid, aname, password)
        )
        
        conn.commit()
        conn.close()
        flash('新管理员账号创建成功！', 'success')
    except Exception as e:
        flash('创建管理员失败！', 'error')
        print(f"添加管理员错误: {e}")
    
    return redirect(url_for('admin_manage'))

# ==================== 6.5 系统设置与数据备份（管理员专属） ====================
@app.route('/admin/settings')
@login_required
@role_required(3)
def admin_settings():
    """系统设置页面（管理员专属）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取系统统计信息
        stats = {}
        
        # 学生总数
        cursor.execute("SELECT COUNT(*) FROM Student")
        stats['student_count'] = cursor.fetchone()[0]
        
        # 教师总数
        cursor.execute("SELECT COUNT(*) FROM Teacher WHERE Status = 1")
        stats['teacher_count'] = cursor.fetchone()[0]
        
        # 院系总数
        cursor.execute("SELECT COUNT(*) FROM Department")
        stats['dept_count'] = cursor.fetchone()[0]
        
        # 课程总数
        cursor.execute("SELECT COUNT(*) FROM Course")
        stats['course_count'] = cursor.fetchone()[0]
        
        # 成绩记录总数
        cursor.execute("SELECT COUNT(*) FROM Grade")
        stats['score_count'] = cursor.fetchone()[0]
        
        # 待审核教师数
        cursor.execute("SELECT COUNT(*) FROM Teacher WHERE Status = 0")
        stats['pending_teachers'] = cursor.fetchone()[0]
        
        conn.close()
        
        return render_template('admin_settings.html', stats=stats)
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"系统设置错误: {e}")
        return render_template('admin_settings.html', stats={})

@app.route('/admin/backup', methods=['POST'])
@login_required
@role_required(3)
def admin_backup():
    """数据备份功能（管理员专属）"""
    try:
        import json
        from datetime import datetime
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        backup_data = {
            'backup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tables': {}
        }
        
        # 备份各表数据
        tables = ['Department', 'Major', 'Class', 'Student', 'Teacher', 'SysAdmin', 'Course', 'Grade', 'Award_punish', 'SystemLog']
        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                backup_data['tables'][table] = {
                    'columns': columns,
                    'rows': [list(row) for row in rows]
                }
            except Exception as e:
                print(f"备份{table}表失败: {e}")
        
        conn.close()
        
        # 生成备份文件名
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 保存到备份目录
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        backup_path = os.path.join(backup_dir, backup_filename)
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        flash(f'数据备份成功！文件名：{backup_filename}', 'success')
        
        # 返回备份文件下载
        from flask import send_file
        return send_file(backup_path, as_attachment=True, download_name=backup_filename)
        
    except Exception as e:
        flash(f'数据备份失败：{str(e)}', 'error')
        print(f"数据备份错误: {e}")
        return redirect(url_for('admin_settings'))

@app.route('/admin/clear_logs', methods=['POST'])
@login_required
@role_required(3)
def admin_clear_logs():
    """清理系统日志（管理员专属）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 删除一定时间前的操作日志（例如30天前）
        cursor.execute("DELETE FROM SystemLog WHERE OpTime < DATEADD(day, -30, GETDATE())")
        conn.commit()
        conn.close()
        flash('系统日志清理完成！', 'success')
    except Exception as e:
        flash(f'清理失败：{str(e)}', 'error')
        print(f"清理日志错误: {e}")
    
    return redirect(url_for('admin_settings'))


# ==================== 7.5 奖惩记录路由（使用C_Award_punish视图）====================
@app.route('/award')
@login_required
def award():
    """奖惩记录页面（使用C_Award_punish视图）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 使用C_Award_punish视图查询奖惩记录
        cursor.execute("""
            SELECT Sno, Sname, Cid, Cname, Mid, Mname, Did, Dname,
                   Aid, Aname, Aproject
            FROM C_Award_punish
            ORDER BY Sno, Aid
        """)
        awards = cursor.fetchall()

        conn.close()

        return render_template('award.html', awards=awards)
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"奖惩记录错误: {e}")
        return render_template('award.html', awards=[])


# ==================== 7.1 学生信息查询路由（使用A_Student视图）====================
@app.route('/student_query')
@login_required
def student_query():
    """学生信息查询页面（使用A_Student视图）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取查询参数
        search_sno = request.args.get('search_sno', '').strip()
        search_name = request.args.get('search_name', '').strip()
        search_dept = request.args.get('search_dept', '').strip()

        # 获取院系列表（用于下拉框）
        cursor.execute("SELECT Did, Dname FROM Department ORDER BY Did")
        departments = cursor.fetchall()

        # 查询学生信息（使用A_Student视图）
        if search_sno or search_name or search_dept:
            sql = "SELECT * FROM A_Student WHERE 1=1"
            params = []
            if search_sno:
                sql += " AND Sno LIKE ?"
                params.append(f"%{search_sno}%")
            if search_name:
                sql += " AND Sname LIKE ?"
                params.append(f"%{search_name}%")
            if search_dept:
                sql += " AND Did = ?"
                params.append(search_dept)
            sql += " ORDER BY Sno"
            cursor.execute(sql, params)
        else:
            cursor.execute("SELECT * FROM A_Student ORDER BY Sno")

        students = cursor.fetchall()
        conn.close()

        return render_template('student_query.html',
                             students=students,
                             departments=departments,
                             search_sno=search_sno,
                             search_name=search_name,
                             search_dept=search_dept)
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"学生查询错误: {e}")
        return render_template('student_query.html', students=[], departments=[])


# ==================== 7. 个人信息路由 ====================
@app.route('/userinfo')
@login_required
def userinfo():
    """个人中心页面"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user_id = session.get('user_id')
        role = session.get('role')
        
        # 获取用户基本信息 - 根据角色查询不同表
        user = None
        nation = None
        if role == 1:  # 学生（使用A_Student视图获取完整信息）
            cursor.execute("SELECT * FROM A_Student WHERE Sno = ?", (user_id,))
            user = cursor.fetchone()
            # 单独查询民族（A_Student视图未包含Nation）
            try:
                cursor.execute("SELECT Nation FROM Student WHERE Sno = ?", (user_id,))
                nation_row = cursor.fetchone()
                if nation_row:
                    nation = nation_row[0]
            except:
                nation = None
        elif role == 2:  # 教师
            cursor.execute("SELECT Tid, Tname FROM Teacher WHERE Tid = ?", (user_id,))
            user = cursor.fetchone()
        elif role == 3:  # 管理员
            cursor.execute("SELECT Aid, Aname FROM SysAdmin WHERE Aid = ?", (user_id,))
            user = cursor.fetchone()
        
        user_scores = []
        score_stats = {'avg': 0, 'max': 0, 'min': 0, 'count': 0}  # 默认值
        
        # 如果是学生，查询成绩
        if role == 1:
            try:
                # 使用存储过程查询成绩单
                cursor.execute("{CALL usp_GetStudentTranscript (?)}", (user_id,))
                user_scores = cursor.fetchall()
                
                # 计算成绩统计
                if user_scores:
                    scores = [s[3] for s in user_scores]  # Score在第5列（索引4）
                    score_stats = {
                        'avg': round(sum(scores) / len(scores), 2),
                        'max': max(scores),
                        'min': min(scores),
                        'count': len(scores)
                    }
            except Exception as e:
                print(f"成绩单查询失败: {e}")
        
        conn.close()
        
        return render_template('userinfo.html',
                             user=user,
                             nation=nation,
                             user_scores=user_scores,
                             score_stats=score_stats,
                             login_time=session.get('login_time'))
    except Exception as e:
        flash('数据加载失败！', 'error')
        print(f"个人中心错误: {e}")
        return render_template('userinfo.html', user=None, user_scores=[], 
                               score_stats={'avg': 0, 'max': 0, 'min': 0, 'count': 0})
# ==================== 7. 角色切换功能（仅管理员可用） ====================
@app.route('/switch_role/<int:role>')
@login_required
@role_required(3)  # 仅管理员可以切换角色
def switch_role(role):
    """快速切换角色（仅管理员可用，用于测试不同权限）"""
    if role not in [1, 2, 3]:
        flash('无效的角色！', 'error')
        return redirect(url_for('index'))
    
    role_names = {1: '学生', 2: '教师', 3: '管理员'}
    session['role'] = role
    flash(f'已切换为【{role_names[role]}】角色', 'success')
    return redirect(url_for('index'))

# ==================== 8. 错误处理 ====================
@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    flash('页面不存在！', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    flash('服务器错误，请稍后重试！', 'error')
    return redirect(url_for('index'))

# ==================== 8. 模板上下文处理器 ====================
@app.context_processor
def inject_globals():
    """向所有模板注入全局变量"""
    return {
        'current_year': datetime.now().year,
        'app_name': '学生成绩管理系统'
    }

# ==================== 数据库初始化 ====================
def init_database():
    """初始化数据库表和初始数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建 Teacher 表（如果不存在）
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Teacher' AND xtype='U')
            CREATE TABLE Teacher (
                Tid varchar(20) PRIMARY KEY,
                Tname varchar(30) NOT NULL,
                Did varchar(20) NOT NULL,
                UserPwd varchar(50) NOT NULL,
                Status int DEFAULT 0 CHECK(Status IN (0,1))
            )
        """)
        
        # 创建 SysAdmin 表（如果不存在）
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SysAdmin' AND xtype='U')
            CREATE TABLE SysAdmin (
                Aid varchar(20) PRIMARY KEY,
                Aname varchar(30) NOT NULL,
                UserPwd varchar(50) NOT NULL
            )
        """)
        
        # 创建初始管理员账号（如果不存在）
        cursor.execute("SELECT Aid FROM SysAdmin WHERE Aid = 'admin'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO SysAdmin (Aid, Aname, UserPwd)
                VALUES ('admin', '系统管理员', 'admin123')
            """)
            print("✓ 初始管理员账号已创建：admin / admin123")
        
        conn.commit()
        conn.close()
        print("✓ 数据库初始化完成")
        return True
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        return False

# ==================== 启动应用 ====================
if __name__ == '__main__':
    # 生产环境请使用 waitress 或 gunicorn
    # from waitress import serve
    # serve(app, host='0.0.0.0', port=5000)
    
    # 初始化数据库
    print("正在初始化数据库...")
    init_database()
    
    # 使用 7777 端口，避免与其他服务冲突
    print("=" * 50)
    print("学生成绩管理系统服务器")
    print("=" * 50)
    print("请访问: http://127.0.0.1:7777")
    print("=" * 50)
    try:
        app.run(debug=True, host='127.0.0.1', port=9999, use_reloader=False)
    except Exception as e:
        print(f"启动失败: {e}")
        input("按回车键退出...")