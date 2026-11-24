// Ezan Vakti — masaüstü widget'ı ve panel göstergesinin ortak kodu.
// Her iki xlet klasörüne sembolik bağ olarak girer: require('./ortak')
//
// Veriyi Python tarafı (bin/ezan-vakti) indirir ve ~/.cache/ezan-vakti/ altına yazar;
// buradaki kod yalnızca okur, dosyaları izler ve gerekirse Python tarafına iş yaptırır.

const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Util = imports.misc.util;

const CONFIG_DIR = GLib.build_filenamev([GLib.get_user_config_dir(), "ezan-vakti"]);
const CACHE_DIR = GLib.build_filenamev([GLib.get_user_cache_dir(), "ezan-vakti"]);
const CLI = GLib.build_filenamev([GLib.get_home_dir(), ".local", "bin", "ezan-vakti"]);
const SES_PID = GLib.build_filenamev([CACHE_DIR, "ses.pid"]);
const RETRY_MS = 10 * 60 * 1000;
const IZLENEN = /^(konum|ayarlar)\.json$|^vakitler-.*\.json$|^bugun\.json$/;

const VAKITLER = [
    { id: "imsak",  ad: "İmsak",  yonelme: "İmsak'a",   api: "Imsak"  },
    { id: "gunes",  ad: "Güneş",  yonelme: "Güneş'e",   api: "Gunes"  },
    { id: "ogle",   ad: "Öğle",   yonelme: "Öğle'ye",   api: "Ogle"   },
    { id: "ikindi", ad: "İkindi", yonelme: "İkindi'ye", api: "Ikindi" },
    { id: "aksam",  ad: "Akşam",  yonelme: "Akşam'a",   api: "Aksam"  },
    { id: "yatsi",  ad: "Yatsı",  yonelme: "Yatsı'ya",  api: "Yatsi"  },
];

function pad(n) { return (n < 10 ? "0" : "") + n; }
function dayKey(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function atTime(key, hhmm) {
    let [y, m, d] = key.split("-").map(Number);
    let [h, min] = hhmm.split(":").map(Number);
    return new Date(y, m - 1, d, h, min, 0, 0);
}
function formatCountdown(ms, withSeconds = true) {
    let s = Math.max(0, Math.floor(ms / 1000));
    if (withSeconds)
        return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
    return `${Math.floor(s / 3600)}:${pad(Math.floor(s / 60) % 60)}`;
}
function titleCase(s) {
    return (s || "").toLocaleLowerCase("tr-TR")
        .replace(/(^|[\s\/(-])(\S)/g, (m, p, c) => p + c.toLocaleUpperCase("tr-TR"));
}
function readJson(path) {
    try {
        let [ok, bytes] = GLib.file_get_contents(path);
        return ok ? JSON.parse(new TextDecoder().decode(bytes)) : null;
    } catch (e) {
        return null;
    }
}
// Derin birleştirme: taban + üst (üstteki değerler kazanır)
function merge(base, over) {
    if (!over || typeof over !== "object" || Array.isArray(over)) return over === undefined ? base : over;
    let out = Object.assign({}, base);
    for (let k in over)
        out[k] = (base && typeof base[k] === "object" && !Array.isArray(base[k])) ? merge(base[k], over[k]) : over[k];
    return out;
}
function launchApp(args) {
    Util.spawn([CLI].concat(args || []));
}
function sesCaliyor() {
    return GLib.file_test(SES_PID, GLib.FileTest.EXISTS);
}

// Proje klasörü: ~/.local/bin/ezan-vakti → <proje>/bin/ezan-vakti sembolik bağından bulunur
function projeDizini() {
    try {
        let hedef = GLib.file_read_link(CLI);
        return GLib.path_get_dirname(GLib.path_get_dirname(hedef));
    } catch (e) {
        return null;
    }
}
let _varsayilan = null;
function varsayilanAyarlar() {
    if (!_varsayilan) {
        let dir = projeDizini();
        _varsayilan = (dir && readJson(GLib.build_filenamev([dir, "data", "varsayilan-ayarlar.json"]))) || {
            widget_ortak: { opaklik: 70, yazi_rengi: "rgb(255,255,255)", vurgu_rengi: "rgb(242,190,88)" },
            widget_varsayilan: { bolumler: { baslik: true, hicri: true, dini_gun: true, sayac: true, vakitler: true },
                                 arapca: true, boyut: 100, genislik: 0 },
            widgetlar: {},
            panel: { gosterim: "saat", uyari_dk: 15, uyari_rengi: "rgb(242,190,88)" },
        };
    }
    return _varsayilan;
}

// Konum, ayarlar, vakitler ve günün özetini izleyen küçük durum nesnesi.
class EzanVeri {
    constructor(onChange) {
        this.onChange = onChange;
        this.konum = null;
        this.ayar = varsayilanAyarlar();
        this.days = [];
        this.bugun = null;
        this.nextFetchAt = 0;
        this.nextBugunAt = 0;
        this.monitors = [];
        this.timer = 0;
    }

    start() {
        for (let dir of [CONFIG_DIR, CACHE_DIR]) {
            GLib.mkdir_with_parents(dir, 0o755);
            let m = Gio.File.new_for_path(dir).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
            let id = m.connect("changed", (mon, f, other) => {
                let names = [f, other].filter(x => x).map(x => x.get_basename());
                if (!names.some(n => IZLENEN.test(n))) return;
                if (this.timer) GLib.source_remove(this.timer);
                this.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 400, () => {
                    this.timer = 0;
                    this.reload();
                    return GLib.SOURCE_REMOVE;
                });
            });
            this.monitors.push([m, id]);
        }
        this.reload();
    }

    stop() {
        if (this.timer) GLib.source_remove(this.timer);
        this.timer = 0;
        for (let [m, id] of this.monitors) {
            m.disconnect(id);
            m.cancel();
        }
        this.monitors = [];
    }

    reload() {
        this.ayar = merge(varsayilanAyarlar(), readJson(GLib.build_filenamev([CONFIG_DIR, "ayarlar.json"])));
        let k = readJson(GLib.build_filenamev([CONFIG_DIR, "konum.json"]));
        this.konum = k && k.ilceId ? k : null;
        this.days = this.konum
            ? parseDays(readJson(GLib.build_filenamev([CACHE_DIR, `vakitler-${this.konum.ilceId}.json`])))
            : [];
        this.bugun = readJson(GLib.build_filenamev([CACHE_DIR, "bugun.json"]));
        if (this.onChange) this.onChange();
    }

    // Bir widget'ın tam ayarı: ortak varsayılan + o widget'a özel farklar
    widgetAyari(kimlik) {
        return merge(this.ayar.widget_varsayilan, (this.ayar.widgetlar || {})[String(kimlik)] || {});
    }

    konumAdi() {
        if (!this.konum) return "Ezan Vakti";
        let { sehir, ilce } = this.konum;
        return titleCase(ilce && ilce !== sehir ? `${sehir} / ${ilce}` : (sehir || ilce));
    }

    // Eksik ya da eskimiş verileri Python tarafına ürettirir (aralıklı, art arda tetiklemez)
    ensureData(now) {
        if (!GLib.file_test(CLI, GLib.FileTest.EXISTS)) return;
        let key = dayKey(now);
        if ((!this.bugun || this.bugun.tarih !== key) && Date.now() >= this.nextBugunAt) {
            this.nextBugunAt = Date.now() + 60 * 1000;
            Util.spawn([CLI, "bugun"]);
        }
        if (!this.konum || Date.now() < this.nextFetchAt) return;
        let i = this.days.findIndex(d => d.key === key);
        if (i >= 0 && this.days.length - i >= 7) return;
        this.nextFetchAt = Date.now() + RETRY_MS;
        Util.spawn([CLI, "guncelle"]);
    }

    // {today, tomorrow, current, next: {v, at}}
    state(now) {
        let key = dayKey(now);
        let i = this.days.findIndex(d => d.key === key);
        let today = i >= 0 ? this.days[i] : null;
        let tomorrow = i >= 0 && i + 1 < this.days.length ? this.days[i + 1] : null;
        let current = "yatsi", next = null;
        if (today) {
            for (let v of VAKITLER) {
                let at = atTime(today.key, today.times[v.id]);
                if (at <= now) current = v.id;
                else if (!next) next = { v, at };
            }
            if (!next && tomorrow) next = { v: VAKITLER[0], at: atTime(tomorrow.key, tomorrow.times.imsak) };
        }
        return { today, tomorrow, current, next };
    }
}

function parseDays(raw) {
    if (!Array.isArray(raw)) return [];
    return raw.filter(d => d && d.MiladiTarihKisa).map(d => {
        let [dd, mm, yyyy] = d.MiladiTarihKisa.split(".").map(Number);
        let times = {};
        for (let v of VAKITLER) times[v.id] = d[v.api];
        return { key: `${yyyy}-${pad(mm)}-${pad(dd)}`, miladi: d.MiladiTarihUzun, hicri: d.HicriTarihUzun, times };
    }).sort((a, b) => a.key < b.key ? -1 : 1);
}

module.exports = { VAKITLER, CLI, EzanVeri, formatCountdown, launchApp, dayKey, sesCaliyor };
