"""Patient-paired reanalysis of the supplied NPC oART study metrics.

Uses archived composite precision where required and explicit decimal display.
Includes input checks, source provenance and complete S6 export."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import math
import numpy as np
from .constants import (CENTRES,METRICS,TARGETS,SMALL,LARGE,GROUPS,GROUP_LABELS,
                        ENDPOINTS,S6_ORDER,S6_LABELS,STRATEGIES,TIMES,CASE_ORDER,
                        models,expected_n,roi_group,unit)
from .io import unique_index,require_numeric,group_records,write_csv,write_json,finite_number
from .statistics import describe,paired_test,benjamini_hochberg,orient_effect,precision_sample_size
from .display import rounded,quantile_display

KEY=('Centre','Model state','Study ID','ROI','Metric')
CKEY=('Centre','Model state','Study ID','ROI group','Metric')
SUMMARY_KEY=('Centre','ROI','Metric')
TOLERANCE=0.0000500001


def validate_metrics(rows,prospective=False):
    unique_index(rows,KEY,'patient metrics');require_numeric(rows,['Value'],'patient metrics')
    if {r['ROI'] for r in rows}!=set((*SMALL,*LARGE,*TARGETS)) or {r['Metric'] for r in rows}!=set(METRICS):
        raise ValueError('Unexpected ROI/metric coverage')
    codes={};names={}
    for r in rows:
        roi,metric=r['ROI'],r['Metric']
        if r['ROI group']!=roi_group(roi) or r['Unit']!=unit(metric): raise ValueError('ROI group/unit mismatch')
        if r['Value']<0 or (metric=='DSC' and r['Value']>1): raise ValueError('Metric outside logical range')
        code=r.get('ROI code')
        if not isinstance(code,str) or not code.strip(): raise ValueError('Missing ROI code')
        if (roi in codes and codes[roi]!=code) or (code in names and names[code]!=roi):
            raise ValueError('ROI codes must map one-to-one to names')
        codes[roi]=code;names[code]=roi
    groups=group_records(rows,('Centre','Model state','ROI','Metric'))
    if prospective:
        ids={r['Study ID'] for r in rows}
        if len(ids)!=135 or len(rows)!=135*25*3: raise ValueError('Expected 135 complete prospective patients')
        if {r['Centre'] for r in rows}!={'Main centre prospective cohort'} or {r['Model state'] for r in rows}!={'Final clinician-approved contours versus automatic contours'}:
            raise ValueError('Unexpected prospective centre/model labels')
        if len(groups)!=75 or any({r['Study ID'] for r in g}!=ids for g in groups.values()):
            raise ValueError('Incomplete prospective measurements')
    else:
        if {r['Centre'] for r in rows}!=set(CENTRES): raise ValueError('Expected five centres')
        for centre in CENTRES:
            cohorts={}
            if {r['Model state'] for r in rows if r['Centre']==centre}!=set(models(centre)):
                raise ValueError(f'Unexpected model states: {centre}')
            for model in models(centre):
                for roi in (*SMALL,*LARGE,*TARGETS):
                    for metric in METRICS:
                        g=groups.get((centre,model,roi,metric),[]);ids={r['Study ID'] for r in g}
                        if len(g)!=expected_n(centre,roi): raise ValueError(f'Incorrect paired count: {centre}/{roi}/{metric}')
                        category='GTV' if centre=='Main centre' and roi in ('GTVp','GTVn') else 'CTV/OAR'
                        if category in cohorts and cohorts[category]!=ids: raise ValueError('Patient IDs differ across paired conditions')
                        cohorts[category]=ids
            if centre=='Main centre' and cohorts['GTV']&cohorts['CTV/OAR']:
                raise ValueError('Main-centre GTV and CTV/OAR test cohorts must be distinct')
    return codes


def compute_composites(rows):
    """Mean across all fixed constituent organs within the same patient; no rounding."""
    out=[]
    oars=[r for r in rows if r['ROI'] in (*SMALL,*LARGE)]
    unique_index(oars,KEY,'OAR constituents')
    for key,g in sorted(group_records(oars,CKEY).items()):
        members=GROUPS[key[3]]
        if len(g)!=len(members) or {r['ROI'] for r in g}!=set(members):
            raise ValueError(f'Incomplete OAR composite: {key}')
        row=dict(zip(CKEY,key));label=GROUP_LABELS[key[3]]
        row.update({'ROI':label,'ROI group':label,'Value':math.fsum(r['Value'] for r in g)/len(g),
                    'Unit':unit(key[4]),'Number of OARs averaged':len(g),
                    'source_rows':';'.join(str(r['source_row']) for r in g),
                    'source_cells':';'.join(f"H{r['source_row']}" for r in g)})
        out.append(row)
    return out


def check_composites(raw,stored):
    got=unique_index(stored,CKEY,'stored OAR means')
    require_numeric(stored,('Within-patient OAR mean','Number of OARs averaged'),'stored OAR means')
    calc=unique_index(compute_composites(raw),CKEY,'computed OAR means')
    if set(got)!=set(calc): raise ValueError('Missing/unmatched stored OAR means')
    checks=[]
    for key,row in calc.items():
        old=got[key];delta=abs(row['Value']-old['Within-patient OAR mean'])
        passed=(delta<=TOLERANCE and old['Unit']==row['Unit'] and old['Number of OARs averaged']==row['Number of OARs averaged'])
        checks.append({**dict(zip(CKEY,key)),'reported':old['Within-patient OAR mean'],
            'recalculated':row['Value'],'absolute_difference':delta,
            'constituent_count':row['Number of OARs averaged'],
            'source_cell':f"F{old['source_row']}",'within_storage_precision':passed})
    if not all(r['within_storage_precision'] for r in checks): raise ValueError('Stored composites disagree with constituents')
    return checks


def calculate_table(rows,endpoints):
    index=unique_index(rows,KEY,'paired input');groups=group_records(rows,('Centre','ROI','Metric'))
    result=[]
    for centre in CENTRES:
        family=[]
        before,after=models(centre)
        for roi in endpoints:
            for metric in METRICS:
                g=groups.get((centre,roi,metric),[])
                x={r['Study ID']:r['Value'] for r in g if r['Model state']==before}
                y={r['Study ID']:r['Value'] for r in g if r['Model state']==after}
                if set(x)!=set(y) or len(x)!=expected_n(centre,roi): raise ValueError(f'Unmatched pairs: {centre}/{roi}/{metric}')
                ids=sorted(x);stats=paired_test([x[i] for i in ids],[y[i] for i in ids])
                row={'Centre':centre,'ROI group':roi_group(roi),'ROI':roi,'Metric':metric,'Unit':unit(metric),'Paired n':len(ids),'Before model':before}
                for state in ('Before','After'):
                    if state=='After': row['After model']=after
                    for label,name in (('mean','mean'),('SD','sd'),('minimum','minimum'),('maximum','maximum'),('Q1','q1'),('median','median'),('Q3','q3')):
                        row[f'{state} {label}']=stats[state.lower()][name]
                d=stats['difference']
                row.update({'Mean difference (after-before)':d['mean'],'SD of paired differences':d['sd'],
                    '95% CI lower':d['ci_lower'],'95% CI upper':d['ci_upper'],'Two-sided paired t-test P':stats['p']})
                family.append(row)
        qvalues=benjamini_hochberg([r['Two-sided paired t-test P'] for r in family])
        for row,q in zip(family,qvalues): row['BH-adjusted q']=float(q)
        result+=family
    return result


def probability(value):
    """Return (is_upper_bound, bound_or_value). Never invent an exact P from '<'."""
    if isinstance(value,bool): raise ValueError('Boolean P/q value')
    text=str(value).strip();bounded=text.startswith('<')
    try: number=float(text[1:] if bounded else text)
    except (TypeError,ValueError): raise ValueError(f'Invalid P/q value: {value!r}')
    if not math.isfinite(number) or not 0<=number<=1 or (bounded and number==0): raise ValueError('Invalid P/q bound')
    return bounded,number


def significant(value,alpha=.05):
    bounded,number=probability(value)
    if bounded and number>alpha: raise ValueError('P/q bound is too loose to infer significance')
    return number<=alpha if bounded else number<alpha


def compare_summary(calculated,stored,sheet):
    archived=unique_index(stored,SUMMARY_KEY,sheet);calc=unique_index(calculated,SUMMARY_KEY,'recalculated table')
    if set(archived)!=set(calc): raise ValueError(f'Endpoint coverage differs: {sheet}')
    checks=[]
    for key,row in calc.items():
        old=archived[key]
        for label in ('Unit','Before model','After model'):
            if row[label]!=old[label]: raise ValueError(f'{sheet} label mismatch: {key}/{label}')
        for label,value in row.items():
            if label in (*SUMMARY_KEY,'ROI group','Unit','Before model','After model'): continue
            reported=old[label]
            if label in ('Two-sided paired t-test P','BH-adjusted q'):
                bounded,num=probability(reported)
            else:
                bounded=False;num=reported
                if not finite_number(num): raise ValueError(f'{sheet} invalid numeric summary: {key}/{label}')
            passed=(0<=value<num) if bounded else abs(value-num)<=(0 if label=='Paired n' else TOLERANCE)
            checks.append({'sheet':sheet,**dict(zip(SUMMARY_KEY,key)),'field':label,
                'source_row':old['source_row'],'reported':reported,'recalculated':value,
                'within_storage_precision':bool(passed),'comparison':'strict upper bound' if bounded else 'half last decimal unit'})
    return checks


def external_summary(table,stored):
    index=unique_index(table,SUMMARY_KEY,'unrounded S4')
    expected={(f'{c} — {s}',f'{m} {t}') for c in CENTRES[1:] for s in models(c) for m in METRICS for t in ('Mean','Max','Min','Q1','Q2','Q3','STD')}
    actual=unique_index(stored,('Centre/model state','Metric/statistic'),'external summary')
    if set(actual)!=expected: raise ValueError('External summary coverage mismatch')
    names={'Mean':'mean','Max':'maximum','Min':'minimum','Q1':'Q1','Q2':'median','Q3':'Q3','STD':'SD'}
    rois={'Small OAR':GROUP_LABELS['Small OARs'],'Large OAR':GROUP_LABELS['Large OARs'],**{r:r for r in TARGETS}}
    checks=[];out=[]
    for key,old in actual.items():
        centre,model=key[0].split(' — ');metric,stat=key[1].split(' ')
        state='Before' if model==models(centre)[0] else 'After'
        row={'Centre/model state':key[0],'Metric/statistic':key[1]}
        for col,roi in rois.items():
            value=index[(centre,roi,metric)][f'{state} {names[stat]}'];row[col]=value
            if not finite_number(old[col]): raise ValueError('Non-numeric external summary')
            checks.append({'centre':centre,'model':model,'roi':roi,'metric':metric,'statistic':stat,
                'reported':old[col],'recalculated':value,'within_storage_precision':abs(value-old[col])<=TOLERANCE})
        out.append(row)
    return out,checks


def case_values(raw,study_id='MC_R023'):
    rows=[];index=unique_index(raw,KEY,'case input');before,after=models('Main centre')
    for group,roi in CASE_ORDER:
        record={'study_id':study_id,'group':group,'roi':roi}
        for metric in METRICS:
            x=index[('Main centre',before,study_id,roi,metric)];y=index[('Main centre',after,study_id,roi,metric)];m=metric.lower()
            record.update({f'baseline_{m}':x['Value'],f'vag_{m}':y['Value'],
                f'beneficial_change_{m}':(y['Value']-x['Value'])*(1 if metric=='DSC' else -1),
                f'baseline_{m}_cell':f"H{x['source_row']}",f'vag_{m}_cell':f"H{y['source_row']}"})
        rows.append(record)
    return rows


def prospective_descriptives(raw):
    all_rows=[*raw,*compute_composites(raw)];groups=group_records(all_rows,('ROI','Metric'))
    calculated=[];display=[]
    for metric,section in zip(METRICS,'abc'):
        for roi in S6_ORDER:
            g=groups[(roi,metric)];v=[r['Value'] for r in g]
            if len(v)!=135: raise ValueError('S6 requires n=135 for every row')
            stats=describe(v);role='primary' if roi in ENDPOINTS and metric=='DSC' else 'supportive' if metric=='DSC' else 'secondary'
            category='Targets and OAR composites' if roi in ENDPOINTS else 'Individual small OARs' if roi in SMALL else 'Individual large OARs'
            calculated.append({'section':section,'ROI':roi,'Metric':metric,'Unit':unit(metric),
                'endpoint_role':role,'category':category,**stats})
            fmt=lambda k:rounded(stats[k],3)
            display.append({'section':section,'ROI':S6_LABELS.get(roi,roi),'Metric':metric,'Unit':unit(metric),'n':len(v),'category':category,
                'Mean ± s.d.':f"{fmt('mean')} ± {fmt('sd')}",
                '95% CI of the mean':f"{fmt('ci_lower')}–{fmt('ci_upper')}",
                'Median (Q1–Q3)':f"{quantile_display(v,.5)} ({quantile_display(v,.25)}–{quantile_display(v,.75)})",
                'P5–P95':f"{quantile_display(v,.05)}–{quantile_display(v,.95)}"})
    return all_rows,calculated,display


def export_s6_markdown(rows,path):
    lines=['# Supplementary Table S6','', 'Prospective geometric agreement for targets and organs at risk (n = 135).','']
    for section,metric in zip('abc',METRICS):
        lines += [f'## {section}, {metric}'+(' (mm)' if metric!='DSC' else ''),'',
            '| ROI | n | Mean ± s.d. | 95% CI of the mean | Median (Q1–Q3) | P5–P95 |',
            '|---|---:|---:|---:|---:|---:|']
        for r in rows:
            if r['section']==section:
                lines.append('| '+' | '.join(str(r[k]) for k in ('ROI','n','Mean ± s.d.','95% CI of the mean','Median (Q1–Q3)','P5–P95'))+' |')
        lines+=['']
    lines+=['Values compare initial automated predictions with final physician-approved contours. '+
        'Small/large OAR composites are patient-level equally weighted means across 10/11 fixed organ categories. '+
        'Bilateral masks were unioned before the supplied organ-level metrics were calculated; the numerical workbook alone does not verify that mask operation. '+
        'Intervals are pointwise two-sided t-based 95% confidence intervals (134 degrees of freedom), unadjusted for multiplicity. '+
        'Quantiles use linear interpolation and describe patient variability, not uncertainty in a mean. '+
        'Display rounding is decimal half-up to three places; calculations do not round intermediate values.']
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')


def analyse(source,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    raw=source['Retrospective patient metrics'];pro=source['Prospective patient metrics'];stored=source['Patient-level OAR averages']
    if validate_metrics(raw)!=validate_metrics(pro,True): raise ValueError('ROI codes differ across cohorts')
    comp_checks=check_composites(raw,stored)
    archive=[{**r,'ROI':r['ROI group'],'Value':r['Within-patient OAR mean']} for r in stored]
    targets=[r for r in raw if r['ROI'] in TARGETS]
    s4=calculate_table(targets+archive,ENDPOINTS);s5=calculate_table(raw,(*SMALL,*LARGE))
    checks=compare_summary(s4,source['Table S4'],'Table S4')+compare_summary(s5,source['Table S5'],'Table S5')
    write_csv(checks,output/'table_recalculation_checks.csv')
    if not all(r['within_storage_precision'] for r in checks): raise ValueError('Archived table mismatch; see table_recalculation_checks.csv')
    full=calculate_table(targets+compute_composites(raw),ENDPOINTS)
    ext,ext_checks=external_summary(full,source['External-centre summary'])
    write_csv(ext_checks,output/'External_summary_checks.csv')
    if not all(r['within_storage_precision'] for r in ext_checks): raise ValueError('External summary mismatch')
    all_pro,s6,display=prospective_descriptives(pro)
    for name,rows in (('Table_S4',s4),('Table_S5',s5),('OAR_composite_checks',comp_checks),
        ('Table_S4_unrounded_composites_sensitivity',full),('External_centre_summary',ext),
        ('Table_S6',s6),('Table_S6_display',display),('Prospective_all_ROI_descriptives',s6)):
        write_csv(rows,output/f'{name}.csv')
    for section in 'abc':
        write_csv([r for r in s6 if r['section']==section],output/f'Table_S6{section}.csv')
    export_s6_markdown(display,output/'Supplementary_Table_S6.md')
    sensitivity=[]
    for a,b in zip(s4,full):
        for field in ('Before mean','Before SD','After mean','After SD','Mean difference (after-before)',
                      'SD of paired differences','95% CI lower','95% CI upper','Two-sided paired t-test P','BH-adjusted q'):
            if rounded(a[field],4)!=rounded(b[field],4):
                sensitivity.append({**{k:a[k] for k in SUMMARY_KEY},'field':field,'archived_composite_path':a[field],
                    'unrounded_constituent_path':b[field],'absolute_difference':abs(a[field]-b[field])})
    write_csv(sensitivity,output/'Composite_precision_sensitivity.csv')
    timing=source['Prospective timing'];idx=unique_index(timing,('Study ID',),'timing');require_numeric(timing,TIMES,'timing')
    if set(k[0] for k in idx)!={r['Study ID'] for r in pro}: raise ValueError('Timing/metric patient IDs differ')
    for r in timing:
        if min(r[t] for t in TIMES)<0 or abs(r[TIMES[0]]+r[TIMES[1]]-r[TIMES[2]])>1e-9: raise ValueError('Invalid timing or arithmetic sum')
    ts=[{'endpoint':t,'unit':'s',**describe([r[t] for r in timing])} for t in TIMES]
    write_csv(ts,output/'Timing_summary.csv')
    strategy=source['Fig S4 GTVn comparison'];idx=unique_index(strategy,('Study ID','Strategy','Metric'),'GTVn strategies');require_numeric(strategy,['Value'],'GTVn strategies')
    ids={r['Study ID'] for r in raw if r['Centre']=='Main centre' and r['ROI']=='GTVn'}
    if set(idx)!={(p,s,m) for p in ids for s in STRATEGIES for m in METRICS}: raise ValueError('Incomplete GTVn strategies')
    raw_index=unique_index(raw,KEY,'retrospective');reused=0
    for r in strategy:
        m=r['Metric'];v=r['Value']
        if r['Centre']!='Main centre' or r['ROI']!='GTVn' or r['Unit']!=unit(m) or v<0 or (m=='DSC' and v>1): raise ValueError('Invalid GTVn strategy row')
        if r['Strategy']!='Direct DIR propagation':
            model=models('Main centre')[0 if r['Strategy']=='Image-only baseline' else 1]
            if raw_index[('Main centre',model,r['Study ID'],'GTVn',m)]['Value']!=v: raise ValueError('GTVn reuse mismatch')
            reused+=1
    gs=[{'strategy':s,'metric':m,**describe([r['Value'] for r in strategy if r['Strategy']==s and r['Metric']==m])} for s in STRATEGIES for m in METRICS]
    gi=unique_index(gs,('strategy','metric'),'strategy summary');old_summary=unique_index(source['GTVn stored summary'],('Strategy','Metric'),'stored strategy summary')
    if set(gi)!=set(old_summary): raise ValueError('Missing strategy summaries')
    for key,r in old_summary.items():
        g=gi[key]
        for field,target in (('n','n'),('Mean','mean'),('Sample SD','sd')):
            if not finite_number(r[field]) or abs(g[target]-r[field])>(0 if field=='n' else TOLERANCE): raise ValueError('GTVn summary mismatch')
    write_csv(gs,output/'ExtendedDataFigure4b_descriptives.csv');write_csv(case_values(raw),output/'ExtendedDataFigure5_case_values.csv')
    families=[];significance_matches=0
    for name,table in (('Table S4',s4),('Table S5',s5)):
        old=unique_index(source[name],SUMMARY_KEY,name)
        for centre in CENTRES:
            f=[r for r in table if r['Centre']==centre];improved=bad=ns=0
            for r in f:
                sig=r['BH-adjusted q']<.05;orientation=r['Mean difference (after-before)']*(1 if r['Metric']=='DSC' else -1)
                if sig==significant(old[tuple(r[k] for k in SUMMARY_KEY)]['BH-adjusted q']): significance_matches+=1
                if not sig: ns+=1
                elif orientation>0: improved+=1
                elif orientation<0: bad+=1
            families.append({'table':name,'centre':centre,'family_size':len(f),'significant_improvements':improved,'significant_deteriorations':bad,'not_significant':ns})
    write_csv(families,output/'Multiplicity_families.csv')
    report={**source['metadata'],'records':{k:len(v) for k,v in source.items() if isinstance(v,list)},
        'table_cells_verified':len(checks),'paired_comparisons':len(s4)+len(s5),'significance_classifications_matched':significance_matches,
        'composite_values_verified':len(comp_checks),'external_summary_values_verified':len(ext_checks),
        'GTVn_reused_values_verified':reused,'patients_prospective':len(timing),'S6_rows':len(s6),'S6_summary_numbers':len(s6)*9,
        'sample_size':precision_sample_size(),'raw_imaging_verified':False,'clinical_model_execution':False,
        'method':'Patient-paired two-sided t; pointwise t CI; centre-specific BH 18/63 tests; archived S4 composite precision'}
    write_json(report,output/'analysis_validation.json')
    return report
