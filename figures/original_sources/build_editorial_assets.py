"""Redraw manuscript figures and typeset saved tables; no model fitting.

All numbers come from the packaged CSV outputs. Original assets remain intact.
Run through notebook 07C in Antigravity, or execute this file directly.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'manuscript/ieee'
DATA = PAPER / 'data_tables'
FIG = PAPER / 'editorial_figures'
TAB = PAPER / 'editorial_tables'
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)
inputs = set()
outputs = []


def load(name):
    path = (DATA / name).resolve()
    inputs.add(path)
    return pd.read_csv(path)


plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10, 'xtick.labelsize': 10,
    'ytick.labelsize': 10, 'legend.fontsize': 10, 'pdf.fonttype': 42,
    'ps.fonttype': 42, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.axisbelow': True})
BLUE, ORANGE, GRAY = '#0072B2', '#D55E00', '#666666'


def save(fig, stem):
    for suffix in ('pdf', 'png'):
        p = FIG / f'{stem}.{suffix}'
        fig.savefig(p, dpi=300, facecolor='white')
        outputs.append(p)
    plt.close(fig)


# A process diagram, not a simulated perimeter or an empirical timeline.
fig, ax = plt.subplots(figsize=(7.15, 3.8))
ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
ax.text(.02,.96,'(a) NIFC mapped line: one 250 m unit = one model row',weight='bold',va='top')
ax.plot([.08,.92],[.79,.79],color=GRAY,lw=2)
for x in np.linspace(.122,.878,10):
    ax.plot(x,.79,'o',color=BLUE,ms=5)
for x in (.08,.92):
    ax.plot([x,x],[.76,.82],color=GRAY,lw=1)
ax.annotate('',xy=(.206,.86),xytext=(.122,.86),arrowprops={'arrowstyle':'<->','color':BLUE})
ax.text(.164,.875,'25 m',ha='center',color=BLUE)
ax.text(.5,.70,'10 sampling points; each point represents 25 m of mapped line',ha='center')
ax.text(.02,.58,'(b) NIROPS observations at one point: illustrative Held support',weight='bold')
ax.annotate('',xy=(.97,.36),xytext=(.04,.36),arrowprops={'arrowstyle':'->','color':GRAY})
for x,label,state,color in [
    (.16,'July 1, 06:00\nPrediction time','100 m outside',BLUE),
    (.50,'July 2, 06:00\nNext observation','20 m outside: near',ORANGE),
    (.84,'July 3, 06:00\nFollow-up','30 m outside: near',ORANGE)]:
    ax.plot(x,.36,'o',color=color,ms=6)
    ax.text(x,.32,label,ha='center',va='top',linespacing=1.25)
    ax.text(x,.43,state,ha='center',color=color)
ax.text(.5,.095,'July 1 to July 2: 24 h, within the 48 h transition limit',ha='center')
ax.text(.5,.025,'Held support: no state more than 50 m inside from July 2 through record end.',ha='center')
fig.subplots_adjust(left=.015,right=.985,top=.98,bottom=.02)
save(fig,'fig1_study_design')

forward=load('TABLE_5_FORWARD_TEMPORAL_GENERALIZATION_V1.csv')
f=forward[forward.model_id=='FORWARD_FIXED_05C'].sort_values('test_year')
fig,axes=plt.subplots(1,2,figsize=(7.15,3.65))
ax=axes[0]
ax.plot(f.test_year,f.pooled_roc_auc,'o-',color=BLUE,label='Pooled')
ax.plot(f.test_year,f.mixed_incident_macro_roc_auc,'s--',color=ORANGE,label='Within-fire')
ax.axhline(.5,color=GRAY,ls=':',lw=1)
ax.set(title='(a) Forward-year ranking',xlabel='Test year',ylabel='ROC-AUC',ylim=(.40,.80),xticks=f.test_year)
ax.legend(loc='upper right',frameon=False)
ax.grid(axis='y',alpha=.2)
ax=axes[1]
for key,label,color,marker,style in [
    ('FORWARD_FIXED_05C','Forward-year LightGBM',BLUE,'o','-'),
    ('HISTORICAL_PREVALENCE_PRIOR','Held-rate baseline',GRAY,'^',':'),
    ('MIXED_YEAR_PRIMARY_OOF_REFERENCE','Mixed-year reference',ORANGE,'s','--')]:
    r=forward[forward.model_id==key].sort_values('test_year')
    ax.plot(r.test_year,r.incident_macro_brier,marker=marker,ls=style,color=color,label=label)
ax.set(title='(b) Probability error',xlabel='Test year',ylabel='Fire-average Brier score',ylim=(.075,.30),xticks=f.test_year)
ax.legend(loc='upper right',frameon=False)
ax.grid(axis='y',alpha=.2)
fig.tight_layout(w_pad=1.5)
save(fig,'fig2_forward_year_results')

source=load('TABLE_6_PREDICTOR_SOURCE_IMPORTANCE_V1.csv')
labels={'weather':'Forecast weather','fuels_canopy':'Fuels and canopy',
        'observation_process':'Observation context', 'terrain':'Terrain',
        'fire_approach_physical':'Fire approach'}
fig,ax=plt.subplots(figsize=(3.5,2.8))
ax.barh([labels[s] for s in source.source_group],source.oof_shap_fraction*100,color=BLUE,height=.62)
ax.invert_yaxis()
for i,v in enumerate(source.oof_shap_fraction*100):
    ax.text(v+.7,i,f'{v:.1f}%',va='center',fontsize=9)
ax.set(xlim=(0,62),xticks=[0,20,40,60],xlabel='Absolute SHAP share (%)')
ax.grid(axis='x',alpha=.2)
fig.tight_layout()
save(fig,'fig3_predictor_attribution')

reg=load('TABLE_8_PHYSICAL_INPUT_REGIMES_V1.csv')
baseline=reg.incident_balanced_held_rate-reg.delta_held_rate_vs_study_incident_mean
assert np.allclose(baseline,baseline.iloc[0])
fig,ax=plt.subplots(figsize=(7.15,2.8))
ax.errorbar(reg.regime_id,reg.incident_balanced_held_rate,
    yerr=[reg.incident_balanced_held_rate-reg.incident_balanced_held_rate_ci_lower,
          reg.incident_balanced_held_rate_ci_upper-reg.incident_balanced_held_rate],
    fmt='o',color=BLUE,capsize=4,lw=1.3)
ax.axhline(baseline.iloc[0],color=GRAY,ls='--',label='Study fire-average Held rate')
ax.set(ylim=(.5,1),ylabel='Fire-average Held rate',xlabel='Physical regime',
       title='Held rates differ across descriptive physical regimes')
ax.yaxis.set_major_formatter(PercentFormatter(1))
ax.legend(loc='lower right',frameon=False)
ax.grid(axis='y',alpha=.2)
fig.tight_layout()
save(fig,'fig4_physical_regimes')


def esc(s):
    return str(s).replace('&',r'\&').replace('%',r'\%').replace('_',r'\_')


def table(stem,caption,headers,rows,widths,note,wide=True):
    spec=''.join(r'>{\raggedright\arraybackslash}p{'+str(w)+'in}' for w in widths)
    environment='table*' if wide else 'table'
    note_width=r'\textwidth' if wide else r'\columnwidth'
    lines=[r'\begin{'+environment+r'}[!t]',r'\centering\footnotesize\setlength{\tabcolsep}{3pt}',
           r'\caption{'+caption+'}',r'\label{tab:'+stem+'}',r'\begin{tabular}{'+spec+'}',r'\toprule',
           ' & '.join(r'\textbf{'+esc(h)+'}' for h in headers)+r' \\',r'\midrule']
    for row in rows:
        if isinstance(row,str):
            lines += [r'\midrule\multicolumn{'+str(len(headers))+r'}{l}{\textit{'+row+r'}}\\']
        else:lines.append(' & '.join(esc(v) for v in row)+r' \\')
    lines += [r'\bottomrule\end{tabular}',r'\par\smallskip\begin{minipage}{'+note_width+r'}\footnotesize '+note+r'\end{minipage}',r'\end{'+environment+r'}']
    p=TAB/f'{stem}.tex';p.write_text('\n'.join(lines),encoding='utf-8');outputs.append(p)


freeze = load('../provenance_tables/03N_FREEZE_SUMMARY.csv').iloc[0]
contract = load('TABLE_1_COHORT_AND_MODEL_CONTRACT_V1.csv').set_index('item')['value']
table('cohort','Successive selection of the modeling population, 2020--2024.', ['Required checks, cumulative','Units retained','Fires'],[
    ['Supporting length at least 10%; Held additionally has no conflicting evidence',f'{int(freeze.frozen_supported_units):,}',str(int(freeze.frozen_incidents))],
    ['At least half of supporting length identifies the same observation interval',f'{int(freeze.dynamic_timing_eligible_units):,}','382'],
    ['No sampled point inside the fire area at the assigned prediction time',contract['Analysis units'],contract['Wildfire incidents']],
],[4.7,1.1,.8], r'The National Interagency Fire Center supplies outcome labels; National Infrared Operations supplies perimeter sequences. Supporting length is the length represented by points meeting the source-label checks in Section~\ref{sec:timing}. Prediction time is the input timestamp (Section~\ref{sec:predictiontime}). Counts come from saved selection records; the last row is the final study cohort.')

primary=load('TABLE_2_PRIMARY_OOF_PERFORMANCE_V1.csv')
names={'mean_pred':'Mean predicted Held probability','pooled_pr_auc':'Pooled AP','pooled_roc_auc':'Pooled ROC-AUC',
    'pooled_brier':'Pooled Brier score','pooled_log_loss':'Pooled log loss','incident_macro_brier':'Fire-average Brier score',
    'incident_macro_log_loss':'Fire-average log loss','mixed_incident_macro_pr_auc':'Within-fire AP',
    'mixed_incident_macro_roc_auc':'Within-fire ROC-AUC'}
rows=[]
for _,r in primary.iterrows():
    lo,hi=r.incident_cluster_bootstrap_ci_low,r.incident_cluster_bootstrap_ci_high
    rows.append([names[r.metric_id],f'{r.point_estimate:.3f}',f'{lo:.3f}--{hi:.3f}' if pd.notna(lo) else '--'])
table('primary','Primary LightGBM performance on held-out fires; Held is the positive outcome.', ['Metric','Estimate','95% bootstrap interval'],rows,[1.7,.5,.95],
    'AP: average precision. ROC-AUC: area under the receiver operating characteristic curve. Pooled metrics combine all units; fire-average errors weight fires equally. Within-fire ranking averages equally over the 303 fires containing both outcomes. Intervals use 5,000 resamples of complete fires with replacement; dashes indicate intervals not saved.',wide=False)

fixed=load('ALTERNATIVE_MODEL_OOF_METRICS_V1.csv')
model_names={'LIGHTGBM_05C_REFERENCE':'LightGBM (primary)','XGBOOST':'XGBoost','CATBOOST':'CatBoost','HIST_GRADIENT_BOOSTING':'Histogram gradient boosting',
    'EXTRA_TREES':'Extra Trees','EBM':'Explainable boosting machine','ELASTIC_NET_LOGISTIC':'Elastic-net logistic regression'}
keys=['pooled_pr_auc','pooled_roc_auc','pooled_brier','incident_macro_brier','mixed_incident_macro_roc_auc']
rows=['Fixed configurations']
order=['LIGHTGBM_05C_REFERENCE','XGBOOST','CATBOOST','HIST_GRADIENT_BOOSTING','EXTRA_TREES','EBM','ELASTIC_NET_LOGISTIC']
for m in order:
    r=fixed[fixed.model_id==m].iloc[0];rows.append([model_names[m]]+[f'{r[k]:.3f}' for k in keys])
rows+=['Configurations selected by inner validation']
tuned=load('TUNED_CHALLENGER_PROBABILITY_METRICS_V1.csv')
for m,label in [('XGBOOST__TUNED_RAW','XGBoost: tuned, raw'),('XGBOOST__TUNED_CALIBRATED','XGBoost: tuned, calibration selected'),('CATBOOST__TUNED_RAW','CatBoost: tuned, raw'),('CATBOOST__TUNED_CALIBRATED','CatBoost: tuned, calibration selected')]:
    r=tuned[tuned.variant_id==m].iloc[0];rows.append([label]+[f'{r[k]:.3f}' for k in keys])
table('models','Model comparisons on the same held-out fires.', ['Model and setting','Pooled AP','Pooled ROC-AUC','Pooled Brier score','Fire-average Brier score','Within-fire ROC-AUC'], rows,[2.0,.72,.90,.88,1.04,1.06],
    'AP: average precision. ROC-AUC: area under the receiver operating characteristic curve. Higher AP and ROC-AUC and lower Brier scores are better. Pooled metrics combine all units; fire-average and within-fire metrics weight fires equally. Raw means unadjusted probabilities; calibration selected can leave probabilities unchanged in some folds. All comparisons use the same 304,143 units and are exploratory.')

cal=load('TABLE_3_CALIBRATION_DECISION_V1.csv').set_index('metric')
cal_keys=['mean_pred','pooled_pr_auc','pooled_roc_auc','pooled_brier','incident_macro_brier','incident_macro_log_loss']
table('calibration','Primary model before and after logistic calibration.', ['Metric','Raw probabilities','Calibrated probabilities'],
    [[names[k],f'{cal.loc[k,"raw"]:.3f}',f'{cal.loc[k,"nested_calibrated"]:.3f}'] for k in cal_keys],[3.2,1.7,1.7],
    'AP: average precision; ROC-AUC: area under the receiver operating characteristic curve. Logistic adjustments use inner out-of-fold predictions, excluding outer test fires. Raw means unadjusted. Observed Held rate: 0.677. Pooled metrics combine units; fire-average errors weight fires equally.')

split=load('../provenance_tables/FORWARD_TEMPORAL_SPLIT_DESIGN_V1.csv').set_index('test_year')
historical=forward[forward.model_id=='HISTORICAL_PREVALENCE_PRIOR'].set_index('test_year')
rows=[]
for _,r in f.iterrows():
    year=int(r.test_year); s=split.loc[year]
    start,end=int(s.train_start_year),int(s.train_end_year)
    assert end==year-1 and start==2020
    assert int(s.test_units)==int(r.units) and int(s.test_incidents)==int(r.incidents)
    assert np.isclose(s.train_held_rate,historical.loc[year,'mean_pred'])
    training=str(start) if start==end else f'{start}--{end}'
    rows.append([training,str(year),f'{s.train_held_rate:.3f}']+[f'{r[k]:.3f}' for k in ['held_rate','pooled_roc_auc','incident_macro_brier','mixed_incident_macro_roc_auc']])
table('forward','Chronological timeline, baseline probabilities, and LightGBM performance.', ['Training years','Test year','Baseline Held probability','Test Held rate','Pooled ROC-AUC','LightGBM fire-average Brier score','Within-fire ROC-AUC'],
    rows,[.85,.45,1.05,.75,1.1,1.3,1.05],
    'The baseline probability is the training-period Held fraction, assigned unchanged to every test unit; test Held rate is the observed test-year fraction. The last three columns describe LightGBM. ROC-AUC: area under the receiver operating characteristic curve. Pooled ranking combines units; within-fire ranking averages across fires with both outcomes. Fire-average Brier score weights fires equally; baseline errors appear in Fig.~\\ref{fig:forward}. Test sets (units/fires): 2021, 101,517/87; 2022, 31,232/54; 2023, 10,467/47; 2024, 112,331/104.')

pol=load('LEAKAGE_SAFE_TRANSFER_METRICS_V1.csv')
pol=pol[pol.policy.isin(['MAX_PAST_MIXED_INCIDENT_BA','PAST_PPV_AT_LEAST_0_85'])]
assert (pol.selection_end_year==pol.test_year-1).all()
table('policies','Cutoffs selected from past predictions and applied to raw forward-year LightGBM probabilities.', ['Test year','Selection years','Selection rule','Threshold','Precision for Held','Recall for Held','Within-fire balanced accuracy'],
    [[str(int(r.test_year)),('2021' if int(r.test_year)==2022 else f'2021--{int(r.test_year)-1}'),('Maximize balanced accuracy' if r.policy=='MAX_PAST_MIXED_INCIDENT_BA' else 'Target precision of 0.85')]+[f'{r[k]:.3f}' for k in ['threshold','precision_ppv','sensitivity','mixed_incident_macro_balanced_accuracy']] for _,r in pol.iterrows()],
    [.55,.85,1.65,.6,.95,.85,1.1], 'Selection years supply predictions and labels for choosing the threshold; all displayed performance measures use only the test year. Held is positive. Precision is the fraction of predicted Held units recorded Held; recall is the fraction of recorded Held units identified. Within-fire balanced accuracy averages the correctly identified fractions of both classes, then averages across fires with both outcomes. A historical precision target of 0.85 is not a probability threshold of 0.85 and need not be achieved in the test year.')

manifest={'purpose':'Editorial re-expression of saved outputs; no training or recomputation of performance.',
    'inputs':[{'path':str(p.relative_to(PAPER)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(inputs)],
    'outputs':[{'path':str(p.relative_to(PAPER)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in outputs]}
(PAPER/'editorial_asset_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Created three main figures, one supplemental regime figure, and six tables from saved outputs.')
