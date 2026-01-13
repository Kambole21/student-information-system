from flask import Blueprint, render_template, request, jsonify, session, send_file
from app import students_collection, courses_collection, programs_collection, schools_collection, grades_collection, mock_grades_collection
from bson import ObjectId
from datetime import datetime
import pandas as pd
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import csv

bp = Blueprint('grades_modify', __name__)

@bp.route('/grades/modify')
def grades_modify():
    """Grades modification and filtering page"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    academic_years = ['2036/2037','2035/2036','2034/2035','2033/2034','2032/2033','2031/2032','2030/2031','2029/2030','2028/2029','2027/2028','2026/2027','2025/2026', '2024/2025', '2023/2024', '2022/2023', '2021/2022','2020/2021', '2019/2020']
    semesters = ['1', '2']
    exam_types = ['final', 'mock']
    
    # Get unique course codes
    course_codes = courses_collection.distinct('code')
    
    return render_template('grades/grades_modify.html',
                         schools=schools,
                         programs=programs,
                         academic_years=academic_years,
                         semesters=semesters,
                         exam_types=exam_types,
                         course_codes=sorted(course_codes))

@bp.route('/grades/filter_grades', methods=['POST'])
def filter_grades():
    """Filter grades based on multiple criteria"""
    try:
        data = request.get_json()
        
        # Extract filter parameters
        school_id = data.get('school_id')
        program_id = data.get('program_id')
        academic_year = data.get('academic_year')
        semester = data.get('semester')
        exam_type = data.get('exam_type', 'final')
        intake = data.get('intake')
        enrollment_year = data.get('enrollment_year')
        course_code = data.get('course_code')
        
        # Build query for students
        student_query = {'status': 'active'}
        
        if school_id:
            student_query['school_id'] = ObjectId(school_id)
        
        if program_id:
            student_query['program_id'] = ObjectId(program_id)
        
        if intake:
            student_query['intake'] = intake
        
        if enrollment_year:
            student_query['year_of_enrollment'] = enrollment_year
        
        # Get students matching the criteria
        students = list(students_collection.find(student_query))
        
        if not students:
            return jsonify({'grades': [], 'total_count': 0, 'message': 'No students found matching the criteria'})
        
        student_ids = [student['_id'] for student in students]
        
        # Build query for grades
        grades_query = {'student_id': {'$in': student_ids}}
        
        if academic_year:
            grades_query['academic_year'] = academic_year
        
        if semester:
            grades_query['semester'] = semester
        
        # Choose the appropriate collection
        collection = mock_grades_collection if exam_type == 'mock' else grades_collection
        
        # Get grade documents
        grade_docs = list(collection.find(grades_query))
        
        # Process grades data
        grades_data = []
        for grade_doc in grade_docs:
            student = next((s for s in students if s['_id'] == grade_doc['student_id']), None)
            if not student:
                continue
            
            # Get school and program info
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
            
            # Process each grade entry
            for grade_entry in grade_doc.get('grades', []):
                course = courses_collection.find_one({'_id': ObjectId(grade_entry['course_id'])})
                if not course:
                    continue
                
                # Apply course code filter if specified
                if course_code and course_code.upper() not in course.get('code', '').upper():
                    continue
                
                grade_data = {
                    'student_id': str(student['_id']),
                    'student_number': student['student_number'],
                    'student_name': f"{student['f_name']} {student['l_name']}",
                    'school_name': school['name'] if school else 'Unknown',
                    'program_name': program['name'] if program else 'Unknown',
                    'intake': student.get('intake', '1'),
                    'enrollment_year': student.get('year_of_enrollment', 'N/A'),
                    'academic_year': grade_doc['academic_year'],
                    'semester': grade_doc['semester'],
                    'exam_type': exam_type,
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'marks': grade_entry.get('marks'),
                    'grade': grade_entry.get('grade'),
                    'remarks': grade_entry.get('remarks', ''),
                    'entered_at': grade_doc.get('entered_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M'),
                    'published': grade_doc.get('published', False)
                }
                grades_data.append(grade_data)
        
        return jsonify({
            'grades': grades_data,
            'total_count': len(grades_data),
            'message': f'Found {len(grades_data)} grade records'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/export_csv', methods=['POST'])
def export_csv():
    """Export filtered grades to CSV"""
    try:
        data = request.get_json()
        grades_data = data.get('grades', [])
        
        if not grades_data:
            return jsonify({'error': 'No data to export'}), 400
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = ['Student Number', 'Student Name', 'School', 'Program', 'Intake', 
                  'Enrollment Year', 'Academic Year', 'Semester', 'Exam Type', 
                  'Course Code', 'Course Name', 'Marks', 'Grade', 'Remarks', 'Published']
        writer.writerow(headers)
        
        # Write data
        for grade in grades_data:
            writer.writerow([
                grade.get('student_number', ''),
                grade.get('student_name', ''),
                grade.get('school_name', ''),
                grade.get('program_name', ''),
                'January' if grade.get('intake') == '1' else 'July',
                grade.get('enrollment_year', ''),
                grade.get('academic_year', ''),
                grade.get('semester', ''),
                grade.get('exam_type', '').title(),
                grade.get('course_code', ''),
                grade.get('course_name', ''),
                grade.get('marks', ''),
                grade.get('grade', ''),
                grade.get('remarks', ''),
                'Yes' if grade.get('published') else 'No'
            ])
        
        # Prepare response
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'grades_export_{timestamp}.csv'
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/export_pdf', methods=['POST'])
def export_pdf():
    """Export filtered grades to PDF"""
    try:
        data = request.get_json()
        grades_data = data.get('grades', [])
        filters = data.get('filters', {})
        
        if not grades_data:
            return jsonify({'error': 'No data to export'}), 400
        
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        # Title
        title = Paragraph("Grades Report", title_style)
        elements.append(title)
        
        # Filters info
        if filters:
            filter_text = "Filters Applied: "
            filter_parts = []
            if filters.get('school'):
                filter_parts.append(f"School: {filters['school']}")
            if filters.get('program'):
                filter_parts.append(f"Program: {filters['program']}")
            if filters.get('academic_year'):
                filter_parts.append(f"Academic Year: {filters['academic_year']}")
            if filters.get('semester'):
                filter_parts.append(f"Semester: {filters['semester']}")
            if filters.get('exam_type'):
                filter_parts.append(f"Exam Type: {filters['exam_type']}")
            if filters.get('intake'):
                filter_parts.append(f"Intake: {'January' if filters['intake'] == '1' else 'July'}")
            if filters.get('enrollment_year'):
                filter_parts.append(f"Enrollment Year: {filters['enrollment_year']}")
            if filters.get('course_code'):
                filter_parts.append(f"Course Code: {filters['course_code']}")
            
            filter_text += ", ".join(filter_parts)
            filter_paragraph = Paragraph(filter_text, styles['Normal'])
            elements.append(filter_paragraph)
            elements.append(Spacer(1, 20))
        
        # Prepare table data
        table_data = [['Student No.', 'Student Name', 'Course', 'Marks', 'Grade', 'Remarks']]
        
        for grade in grades_data:
            table_data.append([
                grade.get('student_number', ''),
                grade.get('student_name', ''),
                f"{grade.get('course_code', '')} - {grade.get('course_name', '')}",
                str(grade.get('marks', '')) if grade.get('marks') is not None else 'N/A',
                grade.get('grade', ''),
                grade.get('remarks', '')
            ])
        
        # Create table
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        # Footer
        elements.append(Spacer(1, 20))
        footer = Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Records: {len(grades_data)}", styles['Normal'])
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'grades_export_{timestamp}.pdf'
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/get_filter_options')
def get_filter_options():
    """Get dynamic filter options based on selections"""
    try:
        school_id = request.args.get('school_id')
        program_id = request.args.get('program_id')
        
        response_data = {}
        
        # Get programs for selected school
        if school_id:
            programs = list(programs_collection.find({
                'school_id': ObjectId(school_id),
                'status': 'active'
            }))
            response_data['programs'] = [{'id': str(p['_id']), 'name': p['name']} for p in programs]
        
        # Get intake options
        intakes = [
            {'value': '1', 'label': 'January Intake'},
            {'value': '2', 'label': 'July Intake'}
        ]
        response_data['intakes'] = intakes
        
        # Get enrollment years from students
        enrollment_years = students_collection.distinct('year_of_enrollment')
        response_data['enrollment_years'] = sorted([year for year in enrollment_years if year], reverse=True)
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500