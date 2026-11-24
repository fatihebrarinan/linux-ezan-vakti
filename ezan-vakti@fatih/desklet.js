// Ezan Vakti — Cinnamon masaüstü widget'ı (desklet)
// Birden fazla kopya eklenebilir; her kopyanın hangi bölümleri göstereceği uygulamadaki
// Ayarlar sayfasından seçilir (ayarlar.json → widgetlar[<kimlik>]). Widget yalnızca gösterir.

const Desklet = imports.ui.desklet;
const St = imports.gi.St;
const GLib = imports.gi.GLib;
const Pango = imports.gi.Pango;
const Util = imports.misc.util;

const { VAKITLER, EzanVeri, formatCountdown, launchApp, dayKey, sesCaliyor, CLI } = require('./ortak');

const ICERIK = ["ayet", "hadis", "vecize"];
const SADE_GENISLIK = 240;

class EzanVaktiDesklet extends Desklet.Desklet {
    constructor(metadata, deskletId) {
        super(metadata, deskletId);
        this.setHeader("Ezan Vakti");
        this.box = new St.BoxLayout({ vertical: true, style_class: "ezan-box" });
        this.setContent(this.box);
        this.veri = new EzanVeri(() => this._rebuild());
        this._buildMenu();
    }

    // ---------- Cinnamon menüsü: Yapılandır ve Hakkında uygulamaya gider ----------

    _buildMenu() {
        this._menu.addAction("Ezan Vakti'ni aç", () => launchApp());
        this._menu.addAction("Konum seç…", () => Util.spawn([CLI, "konum"]));
        this._menu.addAction("Vakitleri yenile", () => Util.spawn([CLI, "guncelle", "--zorla"]));
        this._menu.addAction("Ezanı durdur", () => Util.spawn([CLI, "sustur"]));
    }

    configureDesklet() {
        launchApp(["--sayfa", "ayarlar", "--widget", String(this.instance_id)]);
    }

    openAbout() {
        launchApp(["--sayfa", "hakkinda"]);
    }

    // ---------- Yaşam döngüsü ----------

    on_desklet_added_to_desktop() {
        this.veri.start();
        this.timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._tick();
            return GLib.SOURCE_CONTINUE;
        });
    }

    on_desklet_removed() {
        if (this.timer) GLib.source_remove(this.timer);
        this.timer = 0;
        this.veri.stop();
    }

    on_desklet_clicked() {
        if (sesCaliyor()) Util.spawn([CLI, "sustur"]);  // ezan çalarken tıklamak susturur
    }

    // ---------- Arayüz ----------

    _label(styleClass, wrap = true) {
        let l = new St.Label({ style_class: styleClass });
        if (wrap) {
            l.clutter_text.line_wrap = true;
            l.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
            l.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        }
        return l;
    }

    // Ayar ya da veri değişince widget'ı baştan kurar
    _rebuild() {
        this.box.destroy_all_children();
        let w = this.veri.widgetAyari(this.instance_id);
        let o = this.veri.ayar.widget_ortak;
        let b = w.bolumler || {};
        let k = (w.boyut || 100) / 100;
        this.k = k;
        this.w = w;
        this.accent = o.vurgu_rengi;
        let pt = (n) => `font-size: ${(n * k).toFixed(1)}pt;`;
        let a = Math.max(0, Math.min(100, o.opaklik)) / 100;
        this.parts = {};

        // Genişlik: elle verildiyse o; içerik varsa metnin uzunluğuna göre; yoksa sade genişlik
        let icerikVar = ICERIK.some(x => b[x]);
        let genislik = w.genislik > 0 ? w.genislik : (icerikVar ? this._otomatikGenislik(b, w) : SADE_GENISLIK);
        this.box.style = `width: ${Math.round(genislik * k)}px; ` +
            `background-color: rgba(18,22,30,${a}); color: ${o.yazi_rengi}; ` +
            `padding: ${Math.round(14 * k)}px ${Math.round(16 * k)}px; border-radius: ${Math.round(14 * k)}px; ` +
            `spacing: ${Math.round(10 * k)}px;`;

        if (!this.veri.konum && (b.baslik || b.sayac || b.vakitler)) {
            let btn = new St.Button({ label: "Konum seç…", style_class: "ezan-buton" });
            btn.style = pt(10) + `color: ${this.accent};`;
            btn.connect("clicked", () => Util.spawn([CLI, "konum"]));
            this.box.add_child(btn);
        }

        if (b.baslik || b.hicri) {
            let ust = new St.BoxLayout({ vertical: true, style_class: "ezan-ust" });
            if (b.baslik) {
                this.parts.konum = this._label("ezan-konum");
                this.parts.konum.style = pt(11) + "font-weight: bold;";
                this.parts.tarih = this._label("ezan-soluk");
                this.parts.tarih.style = pt(9);
                ust.add_child(this.parts.konum);
                ust.add_child(this.parts.tarih);
            }
            if (b.hicri) {
                this.parts.hicri = this._label("ezan-soluk");
                this.parts.hicri.style = pt(9);
                ust.add_child(this.parts.hicri);
            }
            this.box.add_child(ust);
        }
        if (b.dini_gun) {
            this.parts.dini = this._label("ezan-dini");
            this.parts.dini.style = pt(9) + `color: ${this.accent}; font-weight: bold;`;
            this.box.add_child(this.parts.dini);
        }
        if (b.sayac) {
            let s = new St.BoxLayout({ vertical: true });
            this.parts.sayac = this._label("ezan-sayac", false);
            this.parts.sayac.style = pt(24) + `font-weight: bold; color: ${this.accent};`;
            this.parts.sayacAlt = this._label("ezan-soluk");
            this.parts.sayacAlt.style = pt(9);
            s.add_child(this.parts.sayac);
            s.add_child(this.parts.sayacAlt);
            this.box.add_child(s);
        }
        if (b.vakitler) {
            let liste = new St.BoxLayout({ vertical: true, style_class: "ezan-liste" });
            this.parts.rows = {};
            for (let v of VAKITLER) {
                let row = new St.BoxLayout({ style_class: "ezan-satir" });
                let ad = new St.Label({ text: v.ad, x_expand: true });
                let saat = new St.Label({ text: "--:--" });
                row.add_child(ad);
                row.add_child(saat);
                liste.add_child(row);
                this.parts.rows[v.id] = { row, ad, saat };
            }
            this.box.add_child(liste);
        }
        for (let tur of ICERIK)
            if (b[tur]) this._icerikBolumu(tur, w, pt);

        this.renderedKey = null;
        this._tick();
    }

    _otomatikGenislik(b, w) {
        // Metin uzadıkça genişler; böylece widget ne çok dar-uzun ne çok geniş olur
        let g = this.veri.bugun || {};
        let uzunluk = 0;
        for (let tur of ICERIK) {
            if (!b[tur] || !g[tur]) continue;
            let x = g[tur];
            uzunluk += (x.meal || x.turkce || x.metin || "").length;
            if (w.arapca && x.arapca) uzunluk += x.arapca.length * 0.8;
        }
        return Math.max(260, Math.min(560, Math.round(19 * Math.sqrt(uzunluk))));
    }

    _icerikBolumu(tur, w, pt) {
        let x = (this.veri.bugun || {})[tur];
        let kutu = new St.BoxLayout({ vertical: true, style_class: "ezan-icerik" });
        // Önünde başka bölüm varsa ince bir çizgiyle ayır
        let ayrac = this.box.get_n_children() > 0
            ? `border-top: 1px solid rgba(255,255,255,0.14); padding-top: ${Math.round(10 * this.k)}px;` : "";
        kutu.style = `spacing: ${Math.round(5 * this.k)}px; ${ayrac}`;
        let baslik = this._label("ezan-soluk", false);
        baslik.text = { ayet: "GÜNÜN AYETİ", hadis: "GÜNÜN HADİSİ", vecize: "GÜNÜN VECİZESİ" }[tur];
        baslik.style = pt(7.5) + "font-weight: bold; letter-spacing: 1px;";
        kutu.add_child(baslik);
        if (!x) {
            let bos = this._label("ezan-soluk");
            bos.text = "Hazırlanıyor…";
            bos.style = pt(9);
            kutu.add_child(bos);
            this.box.add_child(kutu);
            return;
        }
        if (w.arapca && x.arapca) {
            let ar = this._label("ezan-arapca");
            ar.text = x.arapca;
            ar.clutter_text.line_alignment = Pango.Alignment.RIGHT;
            ar.style = pt(14) + "font-family: 'Noto Naskh Arabic', 'Amiri', serif;";
            kutu.add_child(ar);
        }
        let metin = this._label("ezan-metin");
        metin.text = x.meal || x.turkce || x.metin || "";
        metin.style = pt(10);
        kutu.add_child(metin);
        let kaynak = this._label("ezan-soluk");
        kaynak.text = tur === "ayet" ? x.ref : (tur === "hadis" ? `Risale-i Nur › ${x.cite_as}` : x.cite_as);
        kaynak.style = pt(7.5);
        kutu.add_child(kaynak);
        this.box.add_child(kutu);
    }

    // ---------- Zamanlayıcı ----------

    _tick() {
        if (!this.box || !this.parts) return;
        let now = new Date();
        let veri = this.veri;
        let p = this.parts;
        veri.ensureData(now);
        let s = veri.state(now);

        if (p.konum) p.konum.text = veri.konumAdi();
        let key = `${dayKey(now)}|${s.current}`;
        if (this.renderedKey !== key) {
            this.renderedKey = key;
            if (p.tarih) p.tarih.text = s.today ? s.today.miladi : (veri.konum ? "Vakitler bekleniyor…" : "Konum seçilmedi.");
            if (p.hicri) p.hicri.text = s.today ? s.today.hicri : ((veri.bugun || {}).hicri || "");
            if (p.dini) {
                let g = veri.bugun || {};
                let y = g.yaklasan_dini_gun;
                p.dini.text = (g.dini_gunler && g.dini_gunler.length) ? `Bugün: ${g.dini_gunler.join(", ")}`
                    : y ? `${y.ad} — ${y.kalan_gun === 1 ? "yarın" : y.kalan_gun + " gün sonra"}` : "";
                p.dini.visible = !!p.dini.text;
            }
            if (p.rows) this._paintRows(s);
        }
        if (p.sayac) {
            p.sayac.text = s.next ? formatCountdown(s.next.at - now) : "--:--:--";
            p.sayacAlt.text = s.next ? `${s.next.v.yonelme} kalan` : (veri.konum ? "" : "Başlamak için konum seçin");
        }
    }

    _paintRows(s) {
        let k = this.k || 1;
        for (let v of VAKITLER) {
            let r = this.parts.rows[v.id];
            let isCurrent = s.today && v.id === s.current;
            let isNext = s.next && v.id === s.next.v.id;
            r.saat.text = s.today ? s.today.times[v.id] : "--:--";
            r.row.style = `padding: ${Math.round(5 * k)}px ${Math.round(8 * k)}px; border-radius: ${Math.round(8 * k)}px;` +
                (isCurrent ? "background-color: rgba(255,255,255,0.12);" : "");
            let style = `font-size: ${(12 * k).toFixed(1)}pt;` + (isCurrent ? "font-weight: bold;" : "") +
                (isNext ? `color: ${this.accent};` : "");
            r.ad.style = style;
            r.saat.style = style;
        }
    }
}

function main(metadata, deskletId) {
    return new EzanVaktiDesklet(metadata, deskletId);
}
