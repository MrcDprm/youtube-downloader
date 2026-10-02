# YouTube İndirici (YouTube Downloader)

[English](README.md) | **Türkçe**

[yt-dlp](https://github.com/yt-dlp/yt-dlp) ile YouTube videolarını, oynatma listelerini ve sesleri indiren, Python ve Tkinter ile yazılmış bir masaüstü uygulaması. yt-dlp'yi kendisi güncelleyerek çalışmaya devam eder.

> 🚧 Geliştiriliyor. Bu README şimdilik proje planı; v1.0.0'da tamamlanacak.

> ⚠️ **Sadece kişisel kullanım içindir.** Yalnızca sahibi olduğun ya da indirme izni olan videoları indir; YouTube Hizmet Şartları'na ve telif hakkı yasalarına uy.

## Plan

### MVP
- **Linki yapıştır:** Video ya da oynatma listesi linki tanınır (panodan da). İndirmeden önce başlık, kanal, süre ve küçük resim gösterilir.
- **Video ya da ses:** Video seçilen kalitede MP4 olarak (en iyi, 2160p, 1440p, 1080p, 720p, 480p, 360p), ses MP3 ya da M4A olarak.
- **Oynatma listeleri:** Listedeki bütün videolar kuyruğa eklenir.
- **Kuyruk:** İndirmeler sırayla, yüzde, hız ve kalan süreyle yapılır; tek düğme kuyruğu durdurur.
- **Güvenli çıktı:** Var olan dosyaların üzerine yazılmaz, dosya adları Windows için güvenli hâle getirilir, yarım kalan dosyalar temizlenir. Sadece YouTube linkleri kabul edilir.
- **Çalışmaya devam eder:** Uygulama açılışta yeni bir yt-dlp sürümü var mı bakar ve arka planda kurar (sürüm ve SHA-256 özeti PyPI'den). YouTube'un artık istediği JavaScript çalıştırıcısı (Deno) da ilk ihtiyaçta aynı şekilde indirilir.
- **Anlaşılır hatalar:** Gizli, silinmiş, yaş sınırlı ya da bölgeye kapalı videolar ve bağlantı sorunları okunur mesajlarla gösterilir.
- **Kullanım:** Kayıt klasörü (varsayılan İndirilenler), "klasörü aç", koyu ve açık tema, Türkçe ve İngilizce, hatırlanan ayarlar.
- **Masaüstü uygulaması:** İkon, sürüm, kişisel kullanım notlu Hakkında penceresi, kullanıcı klasörüne kaydedilen ayarlar, FFmpeg dahil Windows kurulum dosyası (PyInstaller + Inno Setup).
- **Testler:** Link kontrolü, format seçimi, ilerleme ayrıştırma, güncelleme ve özet kontrolü, ayarlar.

### Gelecek Planları
- Altyazılar.
- Videonun bir bölümünü seçme (başlangıç / bitiş zamanı).
- Aynı anda birden fazla video indirme.
- Kanal indirme.

## Kullanılan Teknolojiler
- Python 3, Tkinter
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (kütüphane olarak) ve YouTube'un JavaScript'i için [Deno](https://deno.com)
- Görüntü ile sesi birleştirmek ve MP3 için [FFmpeg](https://ffmpeg.org)
- Küçük resimler için [Pillow](https://python-pillow.org)
- `unittest`
- PyInstaller, Inno Setup
