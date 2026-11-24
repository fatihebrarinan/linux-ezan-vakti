// Ezan Vakti — Cinnamon panel göstergesi (applet)
// Panelde "Öğle 12:41" / "Öğle'ye 1:23"; vakte az kalınca renk değişir; tıklayınca günün vakitleri.

const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;
const GLib = imports.gi.GLib;
const Util = imports.misc.util;

const { VAKITLER, EzanVeri, formatCountdown, launchApp, CLI } = require('./ortak');

class EzanVaktiApplet extends Applet.TextApplet {
    constructor(metadata, orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);
        this.setAllowedLayout(Applet.AllowedLayout.BOTH);
        this.orientation = orientation;
        this.set_applet_label("Ezan Vakti");
        this.set_applet_tooltip("Ezan Vakti");

        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager.addMenu(this.menu);
        this._buildPopup();
        this.menu.connect("open-state-changed", (m, open) => { if (open) this._tick(true); });

        this.veri = new EzanVeri(() => this._tick(true));
        this.veri.start();
        this.timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._tick(false);
            return GLib.SOURCE_CONTINUE;
        });
    }

    _buildPopup() {
        let box = new St.BoxLayout({ vertical: true, style_class: "ezan-panel-popup" });
        this.pKonum = new St.Label({ style_class: "ezan-panel-konum" });
        this.pTarih = new St.Label({ style_class: "ezan-panel-soluk" });
        this.pSayac = new St.Label({ style_class: "ezan-panel-sayac" });
        this.pSayacAlt = new St.Label({ style_class: "ezan-panel-soluk" });
        for (let l of [this.pKonum, this.pTarih, this.pSayac, this.pSayacAlt]) box.add_child(l);

        let liste = new St.BoxLayout({ vertical: true, style_class: "ezan-panel-liste" });
        this.rows = {};
        for (let v of VAKITLER) {
            let row = new St.BoxLayout({ style_class: "ezan-panel-satir" });
            let ad = new St.Label({ text: v.ad, x_expand: true });
            let saat = new St.Label({ text: "--:--" });
            row.add_child(ad);
            row.add_child(saat);
            liste.add_child(row);
            this.rows[v.id] = { row, ad, saat };
        }
        box.add_child(liste);
        this.menu.addActor(box);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addAction("Ezan Vakti'ni aç", () => launchApp());
        this.menu.addAction("Dini günler", () => launchApp(["--sayfa", "dini"]));
        this.menu.addAction("Ezanı durdur", () => Util.spawn([CLI, "sustur"]));
    }

    // Cinnamon menüsündeki Yapılandır ve Hakkında uygulamaya gider
    configureApplet() {
        launchApp(["--sayfa", "ayarlar", "--bolum", "panel"]);
    }

    openAbout() {
        launchApp(["--sayfa", "hakkinda"]);
    }

    on_applet_clicked() {
        this.menu.toggle();
    }

    on_applet_removed_from_panel() {
        if (this.timer) GLib.source_remove(this.timer);
        this.timer = 0;
        this.veri.stop();
    }

    _tick(force) {
        let now = new Date();
        let veri = this.veri;
        veri.ensureData(now);
        let p = veri.ayar.panel;

        if (!veri.konum) {
            this.set_applet_label("Ezan Vakti");
            this.set_applet_tooltip("Konum seçilmedi — tıklayıp uygulamayı açın");
            this._applet_label.style = "";
            if (this.menu.isOpen || force) this._paintPopup(now, null);
            return;
        }
        let s = veri.state(now);
        if (!s.today || !s.next) {
            this.set_applet_label("Ezan Vakti");
            this._applet_label.style = "";
            if (this.menu.isOpen || force) this._paintPopup(now, s);
            return;
        }

        let kalanMs = s.next.at - now;
        let saat = s.next.v.id === "imsak" && s.tomorrow && s.next.at.getDate() !== now.getDate()
            ? s.tomorrow.times.imsak : s.today.times[s.next.v.id];
        let kalan = formatCountdown(kalanMs, false);
        let label = p.gosterim === "kalan" ? `${s.next.v.yonelme} ${kalan}`
            : p.gosterim === "ikisi" ? `${s.next.v.ad} ${saat} · ${kalan}`
            : `${s.next.v.ad} ${saat}`;
        if (this._lastLabel !== label) {
            this._lastLabel = label;
            this.set_applet_label(label);
        }
        let uyari = p.uyari_dk > 0 && kalanMs <= p.uyari_dk * 60000;
        let style = uyari ? `color: ${p.uyari_rengi}; font-weight: bold;` : "";
        if (this._applet_label.style !== style) this._applet_label.style = style;
        this.set_applet_tooltip(`${s.next.v.yonelme} kalan: ${formatCountdown(kalanMs)}`);

        if (this.menu.isOpen || force) this._paintPopup(now, s);
    }

    _paintPopup(now, s) {
        this.pKonum.text = this.veri.konumAdi();
        if (!s || !s.today) {
            this.pTarih.text = this.veri.konum ? "Vakitler bekleniyor…" : "Konum seçilmedi.";
            this.pSayac.text = "--:--:--";
            this.pSayacAlt.text = "";
            for (let v of VAKITLER) this.rows[v.id].saat.text = "--:--";
            return;
        }
        this.pTarih.text = `${s.today.miladi}\n${s.today.hicri}`;
        this.pSayac.text = s.next ? formatCountdown(s.next.at - now) : "--:--:--";
        this.pSayacAlt.text = s.next ? `${s.next.v.yonelme} kalan` : "";
        let acc = this.veri.ayar.panel.uyari_rengi;
        for (let v of VAKITLER) {
            let r = this.rows[v.id];
            r.saat.text = s.today.times[v.id];
            if (v.id === s.current) r.row.add_style_class_name("ezan-panel-satir-simdiki");
            else r.row.remove_style_class_name("ezan-panel-satir-simdiki");
            let renk = s.next && v.id === s.next.v.id ? `color: ${acc};` : "";
            r.ad.style = renk;
            r.saat.style = renk;
        }
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new EzanVaktiApplet(metadata, orientation, panelHeight, instanceId);
}
