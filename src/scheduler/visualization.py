import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)


class ScheduleVisualizer:
    """
    Classe per la visualizzazione grafica dello scheduling
    """

    def __init__(self, solution_df, tasks_df, output_dir="/app/data"):
        """
        Inizializza il visualizzatore

        Args:
            solution_df: DataFrame con la soluzione dello scheduling
            tasks_df: DataFrame con i task originali
            output_dir: Directory per salvare i grafici
        """
        self.solution_df = solution_df
        self.tasks_df = tasks_df
        self.output_dir = output_dir

        # Assicurati che la directory esista
        os.makedirs(output_dir, exist_ok=True)

        # Configura lo stile matplotlib
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")

    def create_gantt_chart_matplotlib(self, save_path=None):
        """
        Crea un diagramma di Gantt usando matplotlib

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per il grafico")
            return None

        # Verifica che le colonne necessarie esistano
        required_columns = ['task_id', 'task_name', 'user_id', 'date', 'hour']
        missing_columns = [col for col in required_columns if col not in self.solution_df.columns]
        if missing_columns:
            logger.error(f"Colonne mancanti nel DataFrame: {missing_columns}")
            return None

        # Prepara i dati per il Gantt
        gantt_data = []

        for _, row in self.solution_df.iterrows():
            date_str = row['date']
            hour = row['hour']

            # Converti in datetime
            start_time = datetime.strptime(f"{date_str} {hour:02d}:00", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(hours=1)

            gantt_data.append({
                'task_name': row['task_name'],
                'user_id': row['user_id'],
                'start': start_time,
                'end': end_time,
                'task_id': row['task_id']
            })

        gantt_df = pd.DataFrame(gantt_data)

        # Crea il grafico
        fig, ax = plt.subplots(figsize=(15, 8))

        # Ottieni task unici e assegna colori
        unique_tasks = gantt_df['task_name'].unique()
        colors = sns.color_palette("husl", len(unique_tasks))
        task_colors = dict(zip(unique_tasks, colors))

        # Disegna le barre per ogni task
        y_pos = 0
        y_labels = []

        for task_name in unique_tasks:
            task_data = gantt_df[gantt_df['task_name'] == task_name]
            user_id = task_data.iloc[0]['user_id']

            for _, row in task_data.iterrows():
                duration = (row['end'] - row['start']).total_seconds() / 3600  # ore
                ax.barh(y_pos, duration, left=mdates.date2num(row['start']),
                       height=0.6, color=task_colors[task_name], alpha=0.8,
                       edgecolor='black', linewidth=0.5)

            y_labels.append(f"{task_name}\n(User: {user_id})")
            y_pos += 1

        # Configura gli assi
        ax.set_yticks(range(len(unique_tasks)))
        ax.set_yticklabels(y_labels)
        ax.set_xlabel('Data e Ora')
        ax.set_title('Diagramma di Gantt - Pianificazione Task', fontsize=16, fontweight='bold')

        # Formatta l'asse x per le date
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.xticks(rotation=45)

        # Aggiungi griglia
        ax.grid(True, alpha=0.3)

        # Layout
        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "gantt_chart.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Diagramma di Gantt salvato in: {save_path}")

        return save_path

    def create_timeline_chart_plotly(self, save_path=None):
        """
        Crea un grafico timeline interattivo usando Plotly

        Args:
            save_path: Percorso per salvare il grafico HTML
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per il grafico")
            return None

        # Prepara i dati per Plotly
        timeline_data = []

        for _, row in self.solution_df.iterrows():
            date_str = row['date']
            hour = row['hour']

            start_time = datetime.strptime(f"{date_str} {hour:02d}:00", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(hours=1)

            timeline_data.append({
                'Task': row['task_name'],
                'Start': start_time,
                'Finish': end_time,
                'Resource': f"User {row['user_id']}",
                'Task_ID': row['task_id']
            })

        timeline_df = pd.DataFrame(timeline_data)

        # Crea il grafico Gantt con Plotly
        fig = px.timeline(timeline_df,
                         x_start="Start",
                         x_end="Finish",
                         y="Task",
                         color="Resource",
                         title="Timeline Interattiva - Pianificazione Task",
                         hover_data=["Task_ID"])

        # Personalizza il layout
        fig.update_layout(
            height=600,
            xaxis_title="Data e Ora",
            yaxis_title="Task",
            font=dict(size=12),
            title_font_size=16
        )

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "timeline_chart.html")

        fig.write_html(save_path)
        logger.info(f"Timeline interattiva salvata in: {save_path}")

        return save_path

    def create_resource_utilization_chart(self, save_path=None):
        """
        Crea un grafico di utilizzo delle risorse

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per il grafico")
            return None

        # Calcola l'utilizzo per utente e giorno
        utilization_data = []

        for date in self.solution_df['date'].unique():
            day_data = self.solution_df[self.solution_df['date'] == date]

            for user_id in day_data['user_id'].unique():
                user_hours = len(day_data[day_data['user_id'] == user_id])
                utilization_data.append({
                    'date': date,
                    'user_id': user_id,
                    'hours_scheduled': user_hours,
                    'utilization_percent': (user_hours / 8) * 100  # Assumendo 8 ore lavorative
                })

        util_df = pd.DataFrame(utilization_data)

        # Crea il grafico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Grafico 1: Ore programmate per utente per giorno
        pivot_hours = util_df.pivot(index='date', columns='user_id', values='hours_scheduled')
        pivot_hours.plot(kind='bar', ax=ax1, stacked=True)
        ax1.set_title('Ore Programmate per Utente per Giorno')
        ax1.set_xlabel('Data')
        ax1.set_ylabel('Ore Programmate')
        ax1.legend(title='User ID')
        ax1.tick_params(axis='x', rotation=45)

        # Grafico 2: Percentuale di utilizzo
        pivot_util = util_df.pivot(index='date', columns='user_id', values='utilization_percent')
        pivot_util.plot(kind='line', ax=ax2, marker='o')
        ax2.set_title('Percentuale di Utilizzo per Utente')
        ax2.set_xlabel('Data')
        ax2.set_ylabel('Utilizzo (%)')
        ax2.legend(title='User ID')
        ax2.tick_params(axis='x', rotation=45)
        ax2.axhline(y=100, color='r', linestyle='--', alpha=0.7, label='Capacità Massima')

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "resource_utilization.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Grafico utilizzo risorse salvato in: {save_path}")

        return save_path

    def create_task_distribution_chart(self, save_path=None):
        """
        Crea un grafico di distribuzione dei task

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per il grafico")
            return None

        # Calcola statistiche per task
        task_stats = self.solution_df.groupby('task_name').agg({
            'hour': 'count',
            'date': 'nunique',
            'user_id': 'first'
        }).rename(columns={
            'hour': 'total_hours',
            'date': 'days_used'
        })

        # Aggiungi ore pianificate originali
        task_stats = task_stats.merge(
            self.tasks_df[['name', 'planned_hours']].rename(columns={'name': 'task_name'}),
            left_index=True,
            right_on='task_name',
            how='left'
        )

        # Crea subplot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # Grafico 1: Ore totali per task
        task_stats['total_hours'].plot(kind='bar', ax=ax1, color='skyblue')
        ax1.set_title('Ore Totali Programmate per Task')
        ax1.set_ylabel('Ore')
        ax1.tick_params(axis='x', rotation=45)

        # Grafico 2: Giorni utilizzati per task
        task_stats['days_used'].plot(kind='bar', ax=ax2, color='lightgreen')
        ax2.set_title('Giorni Utilizzati per Task')
        ax2.set_ylabel('Giorni')
        ax2.tick_params(axis='x', rotation=45)

        # Grafico 3: Confronto ore pianificate vs programmate
        comparison_data = task_stats[['planned_hours', 'total_hours']].fillna(0)
        comparison_data.plot(kind='bar', ax=ax3)
        ax3.set_title('Confronto: Ore Pianificate vs Programmate')
        ax3.set_ylabel('Ore')
        ax3.legend(['Pianificate', 'Programmate'])
        ax3.tick_params(axis='x', rotation=45)

        # Grafico 4: Distribuzione per utente
        user_distribution = self.solution_df.groupby('user_id')['hour'].count()
        user_distribution.plot(kind='pie', ax=ax4, autopct='%1.1f%%')
        ax4.set_title('Distribuzione Ore per Utente')
        ax4.set_ylabel('')

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "task_distribution.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Grafico distribuzione task salvato in: {save_path}")

        return save_path

    def generate_all_charts(self):
        """
        Genera tutti i grafici disponibili

        Returns:
            dict: Dizionario con i percorsi dei grafici generati
        """
        logger.info("Generazione di tutti i grafici di visualizzazione...")

        charts = {}

        try:
            charts['gantt_chart'] = self.create_gantt_chart_matplotlib()
            charts['timeline_chart'] = self.create_timeline_chart_plotly()
            charts['resource_utilization'] = self.create_resource_utilization_chart()
            charts['task_distribution'] = self.create_task_distribution_chart()

            logger.info(f"Generati {len(charts)} grafici con successo")

        except Exception as e:
            logger.error(f"Errore durante la generazione dei grafici: {str(e)}")

        return charts

    def create_summary_report(self, charts_paths, save_path=None):
        """
        Crea un report HTML con tutti i grafici

        Args:
            charts_paths: Dizionario con i percorsi dei grafici
            save_path: Percorso per salvare il report
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, "scheduling_report.html")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Report Pianificazione Task</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2c3e50; text-align: center; }}
                h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                .chart-container {{ margin: 30px 0; text-align: center; }}
                .chart-container img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
                .stats {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 50px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>📊 Report Pianificazione Task</h1>
            <p><strong>Generato il:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <div class="stats">
                <h3>📈 Statistiche Generali</h3>
                <ul>
                    <li><strong>Task pianificati:</strong> {len(self.solution_df['task_id'].unique()) if self.solution_df is not None else 0}</li>
                    <li><strong>Ore totali programmate:</strong> {len(self.solution_df) if self.solution_df is not None else 0}</li>
                    <li><strong>Giorni coinvolti:</strong> {len(self.solution_df['date'].unique()) if self.solution_df is not None else 0}</li>
                    <li><strong>Utenti coinvolti:</strong> {len(self.solution_df['user_id'].unique()) if self.solution_df is not None else 0}</li>
                </ul>
            </div>
        """

        # Aggiungi i grafici al report
        if 'gantt_chart' in charts_paths and charts_paths['gantt_chart']:
            html_content += f"""
            <h2>📅 Diagramma di Gantt</h2>
            <div class="chart-container">
                <img src="{os.path.basename(charts_paths['gantt_chart'])}" alt="Diagramma di Gantt">
            </div>
            """

        if 'resource_utilization' in charts_paths and charts_paths['resource_utilization']:
            html_content += f"""
            <h2>👥 Utilizzo Risorse</h2>
            <div class="chart-container">
                <img src="{os.path.basename(charts_paths['resource_utilization'])}" alt="Utilizzo Risorse">
            </div>
            """

        if 'task_distribution' in charts_paths and charts_paths['task_distribution']:
            html_content += f"""
            <h2>📊 Distribuzione Task</h2>
            <div class="chart-container">
                <img src="{os.path.basename(charts_paths['task_distribution'])}" alt="Distribuzione Task">
            </div>
            """

        if 'timeline_chart' in charts_paths and charts_paths['timeline_chart']:
            html_content += f"""
            <h2>⏱️ Timeline Interattiva</h2>
            <div class="chart-container">
                <p><a href="{os.path.basename(charts_paths['timeline_chart'])}" target="_blank">
                   🔗 Apri Timeline Interattiva</a></p>
            </div>
            """

        html_content += """
            <div class="footer">
                <p>Generato da Task Scheduler con OrTools</p>
            </div>
        </body>
        </html>
        """

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Report HTML salvato in: {save_path}")
        return save_path
