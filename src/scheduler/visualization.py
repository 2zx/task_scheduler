import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
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

        # Aggiungi ore pianificate originali se disponibili
        if 'planned_hours' in self.tasks_df.columns:
            task_stats = task_stats.merge(
                self.tasks_df[['name', 'planned_hours']].rename(columns={'name': 'task_name'}),
                left_index=True,
                right_on='task_name',
                how='left'
            )
        else:
            # Se non abbiamo planned_hours, usa remaining_hours come fallback
            if 'remaining_hours' in self.tasks_df.columns:
                task_stats = task_stats.merge(
                    self.tasks_df[['name', 'remaining_hours']].rename(columns={'name': 'task_name', 'remaining_hours': 'planned_hours'}),
                    left_index=True,
                    right_on='task_name',
                    how='left'
                )
            else:
                # Aggiungi colonna vuota per evitare errori
                task_stats['planned_hours'] = 0

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

    # ============================================================================
    # NUOVE VISUALIZZAZIONI CALENDARIO
    # ============================================================================

    def create_calendar_heatmap(self, save_path=None):
        """
        Crea una heatmap calendario che mostra l'intensità di lavoro per giorno/ora

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per calendar heatmap")
            return None

        # Prepara i dati per la heatmap
        # Converti date in datetime se necessario
        solution_copy = self.solution_df.copy()
        solution_copy['datetime'] = pd.to_datetime(solution_copy['date'])
        solution_copy['day_name'] = solution_copy['datetime'].dt.strftime('%Y-%m-%d')

        # Conta task per giorno e ora
        heatmap_data = solution_copy.groupby(['day_name', 'hour']).size().reset_index(name='task_count')

        # Crea pivot table per heatmap
        pivot_data = heatmap_data.pivot(index='day_name', columns='hour', values='task_count')
        pivot_data = pivot_data.fillna(0)

        # Crea il grafico
        fig, ax = plt.subplots(figsize=(16, 8))

        # Crea heatmap
        sns.heatmap(pivot_data,
                   annot=True,
                   fmt='g',
                   cmap='YlOrRd',
                   cbar_kws={'label': 'Numero Task'},
                   ax=ax)

        ax.set_title('📅 Calendar Heatmap - Intensità Task per Giorno/Ora', fontsize=16, fontweight='bold')
        ax.set_xlabel('Ora del Giorno')
        ax.set_ylabel('Data')
        ax.tick_params(axis='x', rotation=0)
        ax.tick_params(axis='y', rotation=0)

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "calendar_heatmap.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Calendar heatmap salvato in: {save_path}")

        return save_path

    def create_weekly_distribution(self, save_path=None):
        """
        Crea un grafico della distribuzione settimanale dei task

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per weekly distribution")
            return None

        # Prepara i dati
        solution_copy = self.solution_df.copy()
        solution_copy['datetime'] = pd.to_datetime(solution_copy['date'])
        solution_copy['weekday'] = solution_copy['datetime'].dt.day_name()
        solution_copy['weekday_num'] = solution_copy['datetime'].dt.dayofweek

        # Conta task per giorno della settimana
        weekly_counts = solution_copy.groupby(['weekday', 'weekday_num']).size().reset_index(name='task_count')
        weekly_counts = weekly_counts.sort_values('weekday_num')

        # Crea il grafico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Grafico 1: Distribuzione per giorno della settimana
        bars = ax1.bar(weekly_counts['weekday'], weekly_counts['task_count'],
                      color=sns.color_palette("viridis", len(weekly_counts)))
        ax1.set_title('📊 Distribuzione Task per Giorno della Settimana', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Numero Task')
        ax1.tick_params(axis='x', rotation=45)

        # Aggiungi valori sulle barre
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{int(height)}', ha='center', va='bottom')

        # Grafico 2: Percentuale per giorno
        total_tasks = weekly_counts['task_count'].sum()
        weekly_counts['percentage'] = (weekly_counts['task_count'] / total_tasks) * 100

        bars2 = ax2.bar(weekly_counts['weekday'], weekly_counts['percentage'],
                       color=sns.color_palette("plasma", len(weekly_counts)))
        ax2.set_title('📈 Percentuale Task per Giorno della Settimana', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Percentuale (%)')
        ax2.tick_params(axis='x', rotation=45)

        # Aggiungi linea di riferimento (distribuzione uniforme)
        uniform_percentage = 100 / 7  # ~14.3% per giorno
        ax2.axhline(y=uniform_percentage, color='red', linestyle='--', alpha=0.7,
                   label=f'Distribuzione Uniforme ({uniform_percentage:.1f}%)')
        ax2.legend()

        # Aggiungi valori sulle barre
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{height:.1f}%', ha='center', va='bottom')

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "weekly_distribution.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Weekly distribution salvato in: {save_path}")

        return save_path

    def create_hourly_timeline(self, save_path=None):
        """
        Crea un grafico della distribuzione oraria dei task

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per hourly timeline")
            return None

        # Conta task per ora
        hourly_counts = self.solution_df.groupby('hour').size().reset_index(name='task_count')

        # Crea il grafico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Grafico 1: Distribuzione oraria
        bars = ax1.bar(hourly_counts['hour'], hourly_counts['task_count'],
                      color=sns.color_palette("coolwarm", len(hourly_counts)))
        ax1.set_title('⏰ Distribuzione Task per Ora del Giorno', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Ora del Giorno')
        ax1.set_ylabel('Numero Task')
        ax1.set_xticks(range(int(hourly_counts['hour'].min()), int(hourly_counts['hour'].max()) + 1))

        # Aggiungi valori sulle barre
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{int(height)}', ha='center', va='bottom')

        # Grafico 2: Timeline cumulativa
        hourly_counts_sorted = hourly_counts.sort_values('hour')
        hourly_counts_sorted['cumulative'] = hourly_counts_sorted['task_count'].cumsum()

        ax2.plot(hourly_counts_sorted['hour'], hourly_counts_sorted['cumulative'],
                marker='o', linewidth=2, markersize=6, color='darkblue')
        ax2.fill_between(hourly_counts_sorted['hour'], hourly_counts_sorted['cumulative'],
                        alpha=0.3, color='lightblue')
        ax2.set_title('📈 Timeline Cumulativa Task', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Ora del Giorno')
        ax2.set_ylabel('Task Cumulativi')
        ax2.set_xticks(range(int(hourly_counts['hour'].min()), int(hourly_counts['hour'].max()) + 1))
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "hourly_timeline.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Hourly timeline salvato in: {save_path}")

        return save_path

    def create_resource_calendar(self, save_path=None):
        """
        Crea calendari individuali per ogni risorsa

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per resource calendar")
            return None

        # Prepara i dati
        solution_copy = self.solution_df.copy()
        solution_copy['datetime'] = pd.to_datetime(solution_copy['date'])

        # Ottieni utenti unici
        unique_users = sorted(solution_copy['user_id'].unique())
        num_users = len(unique_users)

        # Calcola layout griglia
        cols = min(3, num_users)
        rows = (num_users + cols - 1) // cols

        # Crea il grafico
        fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 4*rows))
        if num_users == 1:
            axes = [axes]
        elif rows == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        for i, user_id in enumerate(unique_users):
            user_data = solution_copy[solution_copy['user_id'] == user_id]

            # Conta task per giorno per questo utente
            daily_counts = user_data.groupby('date').size().reset_index(name='task_count')
            daily_counts['datetime'] = pd.to_datetime(daily_counts['date'])
            daily_counts = daily_counts.sort_values('datetime')

            ax = axes[i]

            # Crea grafico a barre per questo utente
            bars = ax.bar(range(len(daily_counts)), daily_counts['task_count'],
                         color=sns.color_palette("Set2")[i % 8])

            ax.set_title(f'👤 User {user_id} - Calendario', fontsize=12, fontweight='bold')
            ax.set_xlabel('Giorni')
            ax.set_ylabel('Task/Giorno')

            # Imposta etichette x con date
            ax.set_xticks(range(len(daily_counts)))
            ax.set_xticklabels([d.strftime('%m-%d') for d in daily_counts['datetime']],
                              rotation=45, fontsize=8)

            # Aggiungi valori sulle barre
            for j, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                       f'{int(height)}', ha='center', va='bottom', fontsize=8)

        # Nascondi assi non utilizzati
        for i in range(num_users, len(axes)):
            axes[i].set_visible(False)

        plt.suptitle('📅 Calendari Individuali per Risorsa', fontsize=16, fontweight='bold')
        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "resource_calendar.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Resource calendar salvato in: {save_path}")

        return save_path

    def create_priority_timeline(self, save_path=None):
        """
        Crea un grafico della distribuzione delle priorità nel tempo

        Args:
            save_path: Percorso per salvare il grafico
        """
        if self.solution_df is None or self.solution_df.empty:
            logger.warning("Nessun dato di scheduling disponibile per priority timeline")
            return None

        # Merge con dati task per ottenere priorità
        if self.tasks_df is None or self.tasks_df.empty:
            logger.warning("Nessun dato task disponibile per priority timeline")
            return None

        # Merge solution con tasks per ottenere priority_score
        merged_df = self.solution_df.merge(
            self.tasks_df[['id', 'priority_score']].rename(columns={'id': 'task_id'}),
            on='task_id',
            how='left'
        )

        if merged_df.empty or 'priority_score' not in merged_df.columns:
            logger.warning("Impossibile ottenere dati priorità per priority timeline")
            return None

        # Classifica priorità
        def classify_priority(score):
            if score >= 80:
                return 'Alta (≥80)'
            elif score >= 50:
                return 'Media (50-79)'
            else:
                return 'Bassa (<50)'

        merged_df['priority_class'] = merged_df['priority_score'].apply(classify_priority)
        merged_df['datetime'] = pd.to_datetime(merged_df['date'])

        # Crea il grafico
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Grafico 1: Timeline priorità per giorno
        priority_daily = merged_df.groupby(['date', 'priority_class']).size().unstack(fill_value=0)

        # Ordina le colonne per priorità
        priority_order = ['Alta (≥80)', 'Media (50-79)', 'Bassa (<50)']
        priority_daily = priority_daily.reindex(columns=priority_order, fill_value=0)

        priority_daily.plot(kind='bar', stacked=True, ax=ax1,
                           color=['#d62728', '#ff7f0e', '#2ca02c'])
        ax1.set_title('🎯 Distribuzione Priorità per Giorno', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Data')
        ax1.set_ylabel('Numero Task')
        ax1.legend(title='Priorità')
        ax1.tick_params(axis='x', rotation=45)

        # Grafico 2: Percentuale priorità nel tempo
        priority_daily_pct = priority_daily.div(priority_daily.sum(axis=1), axis=0) * 100
        priority_daily_pct.plot(kind='area', ax=ax2, alpha=0.7,
                               color=['#d62728', '#ff7f0e', '#2ca02c'])
        ax2.set_title('📈 Percentuale Priorità nel Tempo', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Data')
        ax2.set_ylabel('Percentuale (%)')
        ax2.legend(title='Priorità')
        ax2.tick_params(axis='x', rotation=45)
        ax2.set_ylim(0, 100)

        plt.tight_layout()

        # Salva il grafico
        if save_path is None:
            save_path = os.path.join(self.output_dir, "priority_timeline.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Priority timeline salvato in: {save_path}")

        return save_path

    def generate_calendar_charts(self):
        """
        Genera tutti i grafici calendario

        Returns:
            dict: Dizionario con i percorsi dei grafici calendario generati
        """
        logger.info("Generazione di tutti i grafici calendario...")

        calendar_charts = {}

        try:
            calendar_charts['calendar_heatmap'] = self.create_calendar_heatmap()
            calendar_charts['weekly_distribution'] = self.create_weekly_distribution()
            calendar_charts['hourly_timeline'] = self.create_hourly_timeline()
            calendar_charts['resource_calendar'] = self.create_resource_calendar()
            calendar_charts['priority_timeline'] = self.create_priority_timeline()

            logger.info(f"Generati {len(calendar_charts)} grafici calendario con successo")

        except Exception as e:
            logger.error(f"Errore durante la generazione dei grafici calendario: {str(e)}")

        return calendar_charts

    def create_enhanced_summary_report(self, all_charts_paths, save_path=None):
        """
        Crea un report HTML migliorato con tutti i grafici (standard + calendario)

        Args:
            all_charts_paths: Dizionario con i percorsi di tutti i grafici
            save_path: Percorso per salvare il report
        """
        if save_path is None:
            save_path = os.path.join(self.output_dir, f"enhanced_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        html_content = f"""
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>📅 Task Scheduler - Dashboard Calendario Completo</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.5em;
                    font-weight: 300;
                }}
                .header p {{
                    margin: 10px 0 0 0;
                    opacity: 0.9;
                    font-size: 1.1em;
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 25px;
                    border-bottom: 1px solid #e9ecef;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-top: 15px;
                }}
                .stat-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .stat-number {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #667eea;
                    margin-bottom: 5px;
                }}
                .stat-label {{
                    color: #6c757d;
                    font-size: 0.9em;
                }}
                .section {{
                    padding: 30px;
                    border-bottom: 1px solid #e9ecef;
                }}
                .section:last-child {{
                    border-bottom: none;
                }}
                .section h2 {{
                    color: #2c3e50;
                    border-bottom: 3px solid #667eea;
                    padding-bottom: 10px;
                    margin-bottom: 25px;
                    font-size: 1.8em;
                    font-weight: 400;
                }}
                .chart-container {{
                    margin: 25px 0;
                    text-align: center;
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                }}
                .chart-container img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .chart-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                    gap: 30px;
                    margin: 25px 0;
                }}
                .footer {{
                    text-align: center;
                    padding: 30px;
                    background: #2c3e50;
                    color: white;
                }}
                .footer p {{
                    margin: 0;
                    opacity: 0.8;
                }}
                .link-button {{
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 12px 25px;
                    text-decoration: none;
                    border-radius: 25px;
                    margin: 10px;
                    transition: all 0.3s ease;
                }}
                .link-button:hover {{
                    background: #5a6fd8;
                    transform: translateY(-2px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📅 Task Scheduler Dashboard</h1>
                    <p><strong>Generato il:</strong> {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}</p>
                </div>

                <div class="stats">
                    <h3>📈 Statistiche Generali</h3>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">{len(self.solution_df['task_id'].unique()) if self.solution_df is not None else 0}</div>
                            <div class="stat-label">Task Pianificati</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len(self.solution_df) if self.solution_df is not None else 0}</div>
                            <div class="stat-label">Ore Totali</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len(self.solution_df['date'].unique()) if self.solution_df is not None else 0}</div>
                            <div class="stat-label">Giorni Coinvolti</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len(self.solution_df['user_id'].unique()) if self.solution_df is not None else 0}</div>
                            <div class="stat-label">Risorse Utilizzate</div>
                        </div>
                    </div>
                </div>
        """

        # Sezione Visualizzazioni Calendario
        calendar_charts = ['calendar_heatmap', 'weekly_distribution', 'hourly_timeline', 'resource_calendar', 'priority_timeline']
        calendar_found = any(chart in all_charts_paths for chart in calendar_charts)

        if calendar_found:
            html_content += """
                <div class="section">
                    <h2>📅 Distribuzione Calendario</h2>
                    <div class="chart-grid">
            """

            if 'calendar_heatmap' in all_charts_paths and all_charts_paths['calendar_heatmap']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>📅 Calendar Heatmap</h3>
                            <img src="{os.path.basename(all_charts_paths['calendar_heatmap'])}" alt="Calendar Heatmap">
                        </div>
                """

            if 'weekly_distribution' in all_charts_paths and all_charts_paths['weekly_distribution']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>📊 Distribuzione Settimanale</h3>
                            <img src="{os.path.basename(all_charts_paths['weekly_distribution'])}" alt="Weekly Distribution">
                        </div>
                """

            if 'hourly_timeline' in all_charts_paths and all_charts_paths['hourly_timeline']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>⏰ Timeline Oraria</h3>
                            <img src="{os.path.basename(all_charts_paths['hourly_timeline'])}" alt="Hourly Timeline">
                        </div>
                """

            if 'resource_calendar' in all_charts_paths and all_charts_paths['resource_calendar']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>👥 Calendari per Risorsa</h3>
                            <img src="{os.path.basename(all_charts_paths['resource_calendar'])}" alt="Resource Calendar">
                        </div>
                """

            if 'priority_timeline' in all_charts_paths and all_charts_paths['priority_timeline']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>🎯 Timeline Priorità</h3>
                            <img src="{os.path.basename(all_charts_paths['priority_timeline'])}" alt="Priority Timeline">
                        </div>
                """

            html_content += """
                    </div>
                </div>
            """

        # Sezione Grafici Standard
        standard_charts = ['gantt_chart', 'resource_utilization', 'task_distribution']
        standard_found = any(chart in all_charts_paths for chart in standard_charts)

        if standard_found:
            html_content += """
                <div class="section">
                    <h2>📊 Analisi Standard</h2>
                    <div class="chart-grid">
            """

            if 'gantt_chart' in all_charts_paths and all_charts_paths['gantt_chart']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>📅 Diagramma di Gantt</h3>
                            <img src="{os.path.basename(all_charts_paths['gantt_chart'])}" alt="Diagramma di Gantt">
                        </div>
                """

            if 'resource_utilization' in all_charts_paths and all_charts_paths['resource_utilization']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>👥 Utilizzo Risorse</h3>
                            <img src="{os.path.basename(all_charts_paths['resource_utilization'])}" alt="Utilizzo Risorse">
                        </div>
                """

            if 'task_distribution' in all_charts_paths and all_charts_paths['task_distribution']:
                html_content += f"""
                        <div class="chart-container">
                            <h3>📊 Distribuzione Task</h3>
                            <img src="{os.path.basename(all_charts_paths['task_distribution'])}" alt="Distribuzione Task">
                        </div>
                """

            html_content += """
                    </div>
                </div>
            """

        # Timeline Interattiva
        if 'timeline_chart' in all_charts_paths and all_charts_paths['timeline_chart']:
            html_content += f"""
                <div class="section">
                    <h2>⏱️ Timeline Interattiva</h2>
                    <div class="chart-container">
                        <a href="{os.path.basename(all_charts_paths['timeline_chart'])}" target="_blank" class="link-button">
                           🔗 Apri Timeline Interattiva
                        </a>
                        <p>Clicca il link sopra per aprire la timeline interattiva in una nuova finestra</p>
                    </div>
                </div>
            """

        html_content += """
                <div class="footer">
                    <p>🚀 Generato da Task Scheduler con OrTools | Sistema di Profilazione Centralizzato</p>
                </div>
            </div>
        </body>
        </html>
        """

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Enhanced dashboard HTML salvato in: {save_path}")
        return save_path
