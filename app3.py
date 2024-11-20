from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import pandas as pd
from io import BytesIO
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak, Paragraph
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MERGED_FOLDER'] = 'merged'
app.secret_key = 'supersecretkey'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MERGED_FOLDER'], exist_ok=True)


def merge_csv(users_file, details_file):
    try:
        users_df = pd.read_csv(users_file, header=0)
        details_df = pd.read_csv(details_file, header=0)
        merged_df = pd.merge(users_df, details_df, on='user_id', how='inner')
        return merged_df
    except Exception as e:
        print(f"Error merging CSV files: {e}")
        return None


def get_timestamped_filename(original_filename):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    name, ext = os.path.splitext(original_filename)
    return f"{name}_{timestamp}{ext}"


def save_merged_file(merged_df, file_type):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    merged_filename = f"merged_data_{timestamp}.{file_type}"
    merged_file_path = os.path.join(app.config['MERGED_FOLDER'], merged_filename)

    if file_type == 'csv':
        merged_df.to_csv(merged_file_path, index=False)
    elif file_type == 'xlsx':
        with pd.ExcelWriter(merged_file_path, engine='xlsxwriter') as writer:
            merged_df.to_excel(writer, index=False, sheet_name='MergedData')
    elif file_type == 'pdf':
        if merged_df.empty:
            print("The merged DataFrame is empty.")
            return None  # Early return if there's no data

        try:
            # PDF Generation
            doc = SimpleDocTemplate(merged_file_path, pagesize=landscape(letter))
            story = []
            styles = getSampleStyleSheet()

            title = Paragraph("Merged Data Report", styles['Title'])
            story.append(title)

            # Add some space below the title
            story.append(Spacer(1, 12))

            # Convert dataframe to list of lists
            data = [merged_df.columns.tolist()] + merged_df.values.tolist()

            # Define margins and usable width
            left_margin = 0.5 * inch
            right_margin = 0.5 * inch
            usable_width = landscape(letter)[0] - left_margin - right_margin  # Total width minus margins

            # Calculate dynamic column widths based on content length
            col_widths = []
            for col in merged_df.columns:
                max_len = max(merged_df[col].astype(str).apply(len).max(), len(str(col)))
                col_widths.append(max(1.0 * inch, min(2.0 * inch, max_len * 0.10 * inch)))
            print(col_widths)
            # Check if col_widths is empty
            if not col_widths:
                print("Column widths are empty.")
                return None  # Early return if column widths are not determined
            # 计算有多少页
            a = 0
            for i in col_widths:
                a = a+i
                if a > usable_width:
                    a = a - i
                    print(a)
                    a = i
            print(a)
            # Calculate max columns per page based on usable width
            total_col_width = 0
            max_cols_per_page = 0
            max1 = []
            for width in col_widths:
                total_col_width += width
                if total_col_width < usable_width:
                    max_cols_per_page += 1
                else:
                    max1.append(max_cols_per_page)
                    total_col_width=0
                    max_cols_per_page=1
            max1.append(max_cols_per_page)
            print("aa")
            print(max1)
            # Ensure we have columns to display
            if max_cols_per_page == 0:
                print("No columns fit on the page.")
                return None  # Early return if no columns can be displayed

            # Define row handling logic as before
            max_rows_per_page = 10
            rows = len(data)
            cols = len(data[0])
            num_row_pages = (rows // max_rows_per_page) + 1

            num_col_pages = len(max1)
            print(num_col_pages)
            print(len(max1))
            for row_page in range(num_row_pages):
                start_row = row_page * max_rows_per_page
                end_row = min(start_row + max_rows_per_page, rows)
                for col_page in range(num_col_pages):
                    start_col = col_page * max1[col_page]
                    end_col = min(start_col + max1[col_page], cols)

                    # Prepare page data and create the table
                    page_data = [row[start_col:end_col] for row in data[start_row:end_row]]

                    if not page_data or not page_data[0]:  # Check if page_data is empty
                        print("Page data is empty.")
                        continue

                    table = Table(page_data, colWidths=col_widths[start_col:end_col])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ]))

                    story.append(table)

                    # Add page break if not the last row page
                    if row_page < num_row_pages - 1 or col_page < num_col_pages - 1:
                        story.append(PageBreak())

            # Create a spacer to position the footer content
            story.append(Spacer(1, 24))

            footer_content = Paragraph(
                "Related Information: [Your information here]  |  Signature Date: " + datetime.now().strftime('%Y-%m-%d'),
                styles['Normal'])
            story.append(footer_content)
            doc.build(story)
        except Exception as e:
            print(f"Error generating PDF: {e}")

    return merged_file_path




@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'users_file' in request.files and 'details_file' in request.files:
            users_file = request.files['users_file']
            details_file = request.files['details_file']

            users_file_name = get_timestamped_filename(users_file.filename)
            details_file_name = get_timestamped_filename(details_file.filename)

            users_file_path = os.path.join(app.config['UPLOAD_FOLDER'], users_file_name)
            details_file_path = os.path.join(app.config['UPLOAD_FOLDER'], details_file_name)

            users_file.save(users_file_path)
            details_file.save(details_file_path)

            merged_df = merge_csv(users_file_path, details_file_path)
            if merged_df is None:
                flash("Error merging CSV files.", "error")
                return redirect(url_for('index'))

            if 'download_csv' in request.form:
                merged_file_path = save_merged_file(merged_df, 'csv')
                buffer = BytesIO()
                merged_df.to_csv(buffer, index=False)
                buffer.seek(0)
                return send_file(buffer, as_attachment=True, download_name='merged_data.csv', mimetype='text/csv')

            elif 'download_excel' in request.form:
                merged_file_path = save_merged_file(merged_df, 'xlsx')
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    merged_df.to_excel(writer, index=False, sheet_name='MergedData')
                buffer.seek(0)
                return send_file(buffer, as_attachment=True, download_name='merged_data.xlsx',
                                 mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            elif 'download_pdf' in request.form:
                merged_file_path = save_merged_file(merged_df, 'pdf')
                buffer = BytesIO()
                with open(merged_file_path, 'rb') as f:
                    buffer.write(f.read())
                buffer.seek(0)
                return send_file(buffer, as_attachment=True, download_name='merged_data.pdf',
                                 mimetype='application/pdf')

            elif 'show_data' in request.form:
                return render_template('index.html', tables=[merged_df.to_html(classes='data')],
                                       titles=merged_df.columns.values)

        return redirect(url_for('index'))

    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    merged_files = os.listdir(app.config['MERGED_FOLDER'])

    return render_template('index.html', uploaded_files=uploaded_files, merged_files=merged_files)


@app.route('/download/<folder>/<filename>', methods=['GET'])
def download_file(folder, filename):
    folder_path = app.config.get(f'{folder.upper()}_FOLDER')
    file_path = os.path.join(folder_path, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash(f"The file {filename} does not exist.", "error")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
