"""Readable, searchable local roster status exports; no proprietary payloads."""
from collections import Counter
from html import escape
import json


LABELS = {'candidate_pending_device': 'Sudah dibuat — perlu uji Switch',
          'preserved_verified': 'Wajah Barcelona dipertahankan',
          'missing_source': 'Belum: aset sumber tidak lengkap',
          'missing_identity': 'Belum: identitas sumber belum cocok',
          'ambiguous_identity': 'Belum: lebih dari satu identitas cocok',
          'held_unverified_identity': 'Belum: identitas runtime belum terverifikasi',
          'held_conversion': 'Belum: pemeriksaan konversi gagal',
          'held_import': 'Belum: impor UE gagal',
          'held_cook_validation': 'Belum: pemeriksaan hasil cook gagal',
          'held_not_cooked': 'Belum: hasil cook belum diperiksa'}


def reason_label(reason):
    for fragment, label in (
        ('Skin rim needs excessive eye depth clearance', 'Kedalaman mata melebihi batas penyesuaian kelopak'),
        ('Orbital scan needs one enclosed unambiguous recess', 'Rongga kelopak mata belum terbaca dengan pasti'),
        ('opposed shading normals', 'Normal shading mesh sumber bermasalah'),
        ('Missing source eyelid guide', 'Sumber belum punya guide kelopak mata yang sesuai'),
        ('Eye placement differs too far', 'Posisi mata perlu penyesuaian lebih besar dari batas otomatis'),
        ('excessive eye scaling', 'Mata perlu pembesaran berlebihan'),
        ('Eyelid opening requires review', 'Bukaan kelopak mata perlu diperiksa'),
        ('stable globe depth', 'Kedalaman bola mata belum bisa ditentukan dengan aman'),
        ('lower neck is too far', 'Leher sumber terlalu jauh dari acuan tubuh'),
        ('Eyelid rim is missing or non-finite', 'Guide kelopak mata tidak tersedia atau tidak valid'),
        ('sphere-fit contract', 'Bentuk bola mata sumber belum memenuhi acuan fitting'),
        ('non-finite', 'Geometri/guide sumber memiliki angka yang tidak valid'),
        ('no mobile skeleton mapping', 'Tulang sumber belum punya padanan pada rig mobile'),
        ('Missing primary hair', 'Tekstur dasar rambut/aksesori belum tersedia'),
        ('Cooked UV or skin weights changed', 'UV atau bobot tulang berubah saat cook'),
        ('Cooked triangle count changed', 'Jumlah segitiga berubah saat cook'),
        ('Cooked geometry moved', 'Geometri berubah saat cook'),
        ('Cooked geometry dropped', 'Sebagian geometri hilang saat cook')):
        if fragment in reason:
            return label
    return reason


def origin_label(player):
    origin = player.get('batch_origin')
    return ('Konversi tambahan baru' if origin == 'new_conversion' else
            'Hasil batch sebelumnya' if origin == 'reused_verified' else
            'Barcelona dipertahankan' if player['status'] == 'preserved_verified' else '')


def exports(report, destination):
    teams = {t['team_id']: t for t in report['teams']}
    names = {'english_league': 'Liga Inggris', 'spanish_league': 'Liga Spanyol'}
    counts = Counter(p['status'] for p in report['players'])
    version = report.get('version', 'League realface v22')
    done = report['new_faces'] + report['preserved_faces']
    additional = report.get('additional_faces', report['new_faces'])
    reused = report.get('reused_faces', 0)
    recovery=report.get('recovery')
    if recovery is not None:
        (destination/'RECOVERY-STATUS.json').write_text(json.dumps(recovery,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        recovery_text=[f"PEMULIHAN DARI {recovery['baseline']}",
                       f"{recovery['recovered']}/{recovery['targeted']} lolos audit lokal; {recovery['pending']} masih tertahan.",
                       'Belum berarti aset lama/fallback tetap digunakan. Hasil baru masih perlu uji Switch.','']
        for recovered,title in ((True,'BERHASIL DIPULIHKAN'),(False,'MASIH TERTAHAN')):
            recovery_text.append(title)
            for row in sorted(recovery['players'],key=lambda p:p['name'].casefold()):
                if row['recovered']==recovered:
                    recovery_text.append(f"- {row['name']} | BaseId {row['base_id']}"+
                                         (' | '+reason_label(row.get('reason','')) if not recovered else ''))
            recovery_text.append('')
        (destination/'RECOVERY-STATUS.txt').write_text('\n'.join(recovery_text)+'\n',encoding='utf-8')
    coverage = 100 * done / len(report['players']) if report['players'] else 0
    text = [version.upper(),
            f"{len(teams)} tim / {len(report['players'])} pemain unik diaudit.",
            f"{done} tersedia ({coverage:.1f}%): {additional} tambahan baru, {reused} hasil batch sebelumnya, {report['preserved_faces']} Barcelona dipertahankan.",
            'Sudah dibuat berarti lolos audit lokal; pengujian Switch belum selesai.',
            'Belum berarti belum diperbarui dalam batch FL26 ini. Face bawaan/fallback tetap dipakai.', '']
    table = []
    for player in sorted(report['players'], key=lambda p: p['name'].casefold()):
        club = ', '.join(teams[i]['name'] for i in player['team_ids'])
        league = ', '.join(sorted({names.get(teams[i]['category'], teams[i]['category']) for i in player['team_ids']}))
        label = LABELS.get(player['status'], player['status'])
        origin = origin_label(player)
        if origin:
            label += ' / ' + origin
        reason = reason_label(player.get('reason', ''))
        done = player['status'] in ('candidate_pending_device', 'preserved_verified')
        cells = [player['name'], club, league, label, reason]
        table.append('<tr data-state="' + ('done' if done else 'pending') + '" data-origin="' +
                     escape(player.get('batch_origin', 'preserved' if done else 'pending'), quote=True) + '">' +
                     ''.join('<td>' + escape(str(c)) + '</td>' for c in cells) + '</tr>')
    for team in report['teams']:
        text += [names.get(team['category'], team['category']) + ' / ' + team['name'], '=' * 68]
        players = [p for p in report['players'] if team['team_id'] in p['team_ids']]
        for done, heading in [(True, 'SUDAH / DIPERTAHANKAN'), (False, 'BELUM')]:
            selected = [p for p in players if (p['status'] in ('candidate_pending_device', 'preserved_verified')) == done]
            text.append(heading + f' ({len(selected)})')
            for player in sorted(selected, key=lambda p: p['name'].casefold()):
                text.append('- ' + player['name'] + ' | ' + LABELS.get(player['status'], player['status']) +
                            (' | ' + origin_label(player) if origin_label(player) else '') +
                            (' | ' + reason_label(player['reason']) if player.get('reason') else ''))
            text.append('')
    (destination / 'PLAYER-STATUS.txt').write_text('\n'.join(text) + '\n', encoding='utf-8')
    done = report['new_faces'] + report['preserved_faces']
    html = '''<!doctype html><html lang="id"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__VERSION__</title>
<style>body{font:15px system-ui,sans-serif;margin:32px;color:#142649;background:#eff5fc}
main{max-width:1400px;margin:auto}h1{margin-bottom:8px}p{color:#52657e}input,select{padding:12px;border:1px solid #b5c6df;border-radius:8px;font:inherit;margin:12px 8px 16px 0}
input{width:min(440px,75vw)}table{border-collapse:collapse;background:white;width:100%;border-radius:12px}th,td{padding:12px;text-align:left;border-bottom:1px solid #e0e9f5}th{background:#102750;color:white;position:sticky;top:0}td:last-child{max-width:400px;overflow-wrap:anywhere;font-size:13px}tr[data-state=done] td:first-child{border-left:4px solid #009c82}tr[data-state=pending] td:first-child{border-left:4px solid #e49628}.scroll{overflow:auto}small{color:#65778e}</style>
<main><h1>__VERSION__</h1>'''
    html = html.replace('__VERSION__', escape(version))
    html += f'<p>{len(teams)} tim · {len(report["players"])} pemain · {done} sudah/dipertahankan · {len(report["players"])-done} belum</p>'
    html += f'<p>Cakupan {coverage:.1f}% · {additional} tambahan baru · {reused} hasil batch sebelumnya · {report["preserved_faces"]} Barcelona dipertahankan</p>'
    if recovery is not None:
        html += f'<p>Pemulihan batch sebelumnya: {recovery["recovered"]}/{recovery["targeted"]} berhasil · {recovery["pending"]} masih tertahan. <a href="RECOVERY-STATUS.txt">Daftar pemulihan</a></p>'
    html += '<small>Wajah baru sudah lolos audit lokal. Tampilan, animasi dan performa di Switch masih perlu diuji.<br>Belum = belum diperbarui oleh batch FL26 ini. Face bawaan/fallback tetap dipakai.</small><br>'
    html += '<input id="search" placeholder="Cari pemain, tim, liga, atau alasan…" aria-label="Cari pemain"><select id="state" aria-label="Filter status"><option value="">Semua status</option><option value="done">Sudah / dipertahankan</option><option value="pending">Belum</option></select><select id="origin" aria-label="Filter asal hasil"><option value="">Semua hasil</option><option value="new_conversion">Tambahan baru</option><option value="reused_verified">Batch sebelumnya</option><option value="preserved">Barcelona dipertahankan</option></select><span id="count"></span>'
    html += '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + s + '</th>' for s in ('Pemain', 'Tim', 'Liga', 'Status', 'Alasan')) + '</tr></thead><tbody>' + ''.join(table) + '</tbody></table></div>'
    html += '''<script>const rows=[...document.querySelectorAll('tbody tr')],search=document.getElementById('search'),state=document.getElementById('state'),origin=document.getElementById('origin');function filter(){const q=search.value.toLocaleLowerCase('id');let n=0;for(const row of rows){row.hidden=!(row.textContent.toLocaleLowerCase('id').includes(q)&&(!state.value||row.dataset.state===state.value)&&(!origin.value||row.dataset.origin===origin.value));if(!row.hidden)n++;}document.getElementById('count').textContent=n+' pemain';}search.addEventListener('input',filter);state.addEventListener('change',filter);origin.addEventListener('change',filter);filter();</script></main></html>'''
    (destination / 'PLAYER-STATUS.html').write_text(html, encoding='utf-8')
