# Metasploit Framework — Güvenlik Analizi Raporu

**Ad Soyad:** Ali Baran Berktaş  
**Öğrenci Numarası:** 2420191033  
**Ders:** İSÜ - Web Güvenliği  
**Repo:** https://github.com/rapid7/metasploit-framework  
**Analiz Tarihi:** Nisan 2026  

---

## Özet / Amaç

Metasploit Framework, Rapid7 tarafından geliştirilen ve BSD lisansıyla yayımlanan dünyanın en yaygın kullanılan açık kaynak sızma testi (penetration testing) platformudur. Bu rapor, reponun kurulum scriptleri, izolasyon mekanizmaları, CI/CD pipeline yapısı, Docker mimarisi ve kaynak kod akışını güvenlik perspektifinden incelemeyi amaçlamaktadır.

---

## Adım 1: Kurulum ve install.sh Analizi

**Kapsam:** `msfinstall`, `msfupdate`, `Gemfile`, `metasploit-framework.gemspec`

### Bu Dosya Ne Yapıyor?

Metasploit'in kurulum scripti olan `msfinstall`, aşağıdaki yöntemle çalıştırılır:

```bash
curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > msfinstall
chmod 755 msfinstall
./msfinstall
```

Script şu işlemleri gerçekleştirir:
- Sisteme Ruby runtime ve gerekli bağımlılıkları yükler
- PostgreSQL veritabanını başlatır ve ilk şemayı oluşturur (`~/.msf4/db`)
- `msfconsole`, `msfvenom`, `msfdb` gibi bileşenleri PATH'e ekler
- Modül önbelleğini arka planda oluşturur (2-5 dakika sürer)

### Hangi Bağımlılıklar Oluşturuluyor?

`metasploit-framework.gemspec` dosyasından tespit edilen kritik bağımlılıklar:

| Gem / Paket | Amaç | Güvenlik Notu |
|---|---|---|
| `actionpack` | Rails HTTP katmanı | Rails versiyonuna kilitli, güvenlik güncellemeleri manuel |
| `msgpack ~> 1.6.0` | Veri serileştirme | Versiyon kasıtlı sabitlenmiş (build env uyumsuzluğu) |
| `net-imap` | Postgres SASL kimlik doğrulama | Kerberos parsing için kullanılıyor |
| `rack` | HTTP middleware | authlogic cookie uyumsuzluğu nedeniyle pinned |
| `activerecord` | Veritabanı ORM | Rails versiyonuyla senkronize |

### Kritik Soru Analizi

**"Yazılımın indirdiği kaynaklara ne kadar güvenilir? Dışarıdan paket çekerken hash (imza) kontrolü yapıyor mu?"**

- Kurulum scripti `curl | bash` yöntemiyle çalıştırılmaktadır. Bu yöntem, MITM (Man-in-the-Middle) saldırılarına karşı savunmasızdır.
- `Gemfile.lock` dosyası gem versiyonlarını sabitler, ancak indirme sırasında SHA256 doğrulaması yalnızca Bundler'ın RubyGems entegrasyonuna bırakılmıştır.
- `git submodule` ile çekilen bağımlılıklar commit hash ile sabitlendiğinden daha güvenlidir.
- Antivirus yazılımları Metasploit kurulumunu zararlı yazılım olarak algılayabilir; bu durum kurulum ve çalışma zamanında sorunlara yol açabilir.

**Güvenlik Değerlendirmesi:** Orta-Yüksek risk. `curl | bash` yöntemi endüstri standardında kabul görmez; script imza doğrulaması eksiktir.

### SSL/TLS Paket Güvenliği (Senaryo: Paket Muskalar)

Kurulum sırasında `curl` HTTPS üzerinden script indirir. Burada iki kritik nokta vardır:

1. **TLS sertifika doğrulaması:** `curl` varsayılan olarak TLS sertifikasını doğrular (`--cacert` sisteme bağlıdır). Ancak kullanıcı `-k` (insecure) bayrağıyla çalıştırırsa sertifika doğrulaması devre dışı kalır ve MITM saldırısına kapı açılır.

2. **RPC SSL yapılandırması:** `msfrpcd` servisi varsayılan olarak self-signed sertifika kullanır:
   ```bash
   msfrpcd -P şifre -S   # -S = SSL aktif
   # Sertifika: ~/.msf4/ssl/msfrpcd.key + msfrpcd.crt (self-signed)
   ```
   Self-signed sertifika, istemci tarafında doğrulanamaz; bu durum sertifika sahteciliği (certificate spoofing) riskini doğurur.

3. **Gem indirme TLS:** Bundler, RubyGems üzerinden gem indirirken TLS 1.2+ zorunlu kılar. Ancak pinned versiyonlarda güvenlik açığı çıkmış bir gem sürümü kullanılmaya devam edebilir.

**Öneri:** Kurulum sonrası `openssl s_client -connect localhost:55553` komutuyla RPC sertifikasını doğrulayın; self-signed yerine CA imzalı sertifika kullanın.

---

## Adım 2: İzolasyon ve İz Bırakmadan Temizlik

**Kapsam:** `Vagrantfile`, `docker-compose.yml`, `msfdb`, `~/.msf4/` dizini

### Kurulumun Sistemde Bıraktığı İzler

Metasploit kurulumu aşağıdaki kalıcı bileşenler oluşturur:

```
~/.msf4/                    → Tüm oturum geçmişi, loot, kimlik bilgileri
~/.msf4/db/                 → PostgreSQL veritabanı (tüm tarama geçmişi)
~/.msf4/logs/               → Framework logları
/tmp/metasploit-*/          → Geçici exploit payloadları
/var/log/postgresql/        → DB erişim logları
~/.bash_history             → msfconsole komut geçmişi
```

### Temizlik Adımları

Sistemde hiçbir iz kalmaması için uygulanması gereken prosedür:

```bash
# 1. MSF veritabanını durdur ve sıfırla
msfdb stop
msfdb delete

# 2. MSF konfigürasyon ve veri dizinini temizle
rm -rf ~/.msf4/

# 3. Geçici dosyaları temizle
rm -rf /tmp/msf-*
rm -rf /tmp/metasploit-*

# 4. Bash geçmişini temizle
history -c && history -w

# 5. PostgreSQL loglarını temizle (root gerektirir)
sudo truncate -s 0 /var/log/postgresql/*.log

# 6. Ağ bağlantılarını kontrol et
ss -tulnp | grep -E "4444|5555|443"
```

### İzolasyon Önerisi

Metasploit'in temiz ortamda çalıştırılması için en güvenli yöntem VM veya Docker kullanımıdır:

```bash
# Docker ile izole çalıştırma
docker run --rm -it \
  --network=isolated_net \
  -e MSF_UID=$(id -u) \
  rapid7/metasploit-framework msfconsole
```

- `--rm` bayrağı konteyner durduğunda tüm dosya sistemini siler
- `--network=isolated_net` dış ağ erişimini kontrol altına alır
- Port 4444 (varsayılan reverse shell portu) yalnızca gerektiğinde açılmalıdır

**Güvenlik Değerlendirmesi:** Metasploit, çalıştırıldığı ortamda kapsamlı izler bırakır. VM/Docker olmadan host sistemde çalıştırmak forensic analiz için risk oluşturur.

---

## Adım 3: İş Akışları ve CI/CD Pipeline Analizi

**Kapsam:** `.github/workflows/`, `Rakefile`, `Travis CI`, `RSpec test suite`

### CI/CD Pipeline Yapısı

Metasploit Framework, GitHub Actions üzerinde kapsamlı bir CI/CD pipeline kullanır:

**Test Aşamaları:**

```
Push/PR Tetikleyici
       ↓
┌─────────────────┐
│  RuboCop Lint   │  → Kod stili ve güvenlik kuralları kontrolü
└────────┬────────┘
         ↓
┌─────────────────┐
│  RSpec Tests    │  → Unit ve integration testleri
│  (rake spec)    │
└────────┬────────┘
         ↓
┌─────────────────┐
│  SimpleCov      │  → Kod kapsama raporu
│  Coverage       │
└────────┬────────┘
         ↓
┌─────────────────┐
│  Module Lint    │  → Metasploit modülü format doğrulaması
└────────┬────────┘
         ↓
┌─────────────────────┐
│  Merge / Release    │
└─────────────────────┘
```

### Webhook Analizi

**"Webhook nedir ve bu proje özelinde CI/CD akışında tam olarak ne işe yarar?"**

Webhook, GitHub'ın belirli bir olay gerçekleştiğinde (push, PR açma, merge) harici bir URL'ye HTTP POST isteği gönderme mekanizmasıdır.

Metasploit'te webhook akışı:
1. Geliştirici yeni bir modül için PR açar
2. GitHub webhook → CI sunucusuna bildirim gönderir
3. CI pipeline tetiklenir: lint + test + coverage
4. Test sonuçları PR'a yorum olarak yazılır
5. Tüm kontroller geçerse merge izni verilir

**Güvenlik Riski:** Webhook secret'ının güvensiz saklanması veya doğrulanmaması durumunda sahte CI tetiklemeleri mümkündür.

### Test Altyapısı

```ruby
# Rakefile üzerinden çalıştırma
rake spec          # Tüm RSpec testleri
rake spec SPEC=spec/modules/  # Sadece modül testleri
```

Metasploit, RSpec framework'ü ile kapsamlı test süiti yürütür. SimpleCov ile kod kapsama metrikleri raporlanır.

---

## Adım 4: Docker Mimarisi ve Konteyner Güvenliği

**Kapsam:** `Dockerfile`, `docker-compose.yml`, `docker-compose.override.yml`

### Docker İmajı Nasıl İnşa Ediliyor? — Katman Analizi

`Dockerfile` multi-stage build yaklaşımıyla çalışır. Her `RUN`, `COPY`, `ADD` komutu yeni bir **katman (layer)** oluşturur:

```
Katman 1: FROM ubuntu:20.04          → Temel OS imajı (~70MB)
Katman 2: RUN apt-get install ...    → Ruby, build tools (~200MB)
Katman 3: COPY Gemfile* ./           → Bağımlılık tanımları
Katman 4: RUN bundle install         → Tüm gem'ler (~500MB)
Katman 5: COPY lib/ ./lib/           → Framework kaynak kodu
Katman 6: COPY modules/ ./modules/  → Exploit modülleri (~150MB)
Katman 7: CMD ["./msfconsole"]       → Başlangıç komutu
```

**Güvenlik açısından katman riski:** Her katman ayrı bir filesystem snapshot'ıdır. Eğer bir ara katmanda (örn. Katman 4) hassas bilgi (API key, şifre) `RUN` komutuna yazılmışsa, son imajda görünmese bile `docker history` ile o katman okunabilir.

```dockerfile
# 1. Aşama: Builder
FROM ubuntu:20.04 AS builder
RUN apt-get install -y build-essential ruby bundler ruby-dev bison flex autoconf
COPY lib/metasploit/framework/rails_version_constraint.rb $APP_HOME/lib/...
COPY lib/msf/util/helper.rb $APP_HOME/lib/...
RUN bundle install

# 2. Aşama: Runtime (multi-stage ile builder katmanları temizlenir)
FROM ubuntu:20.04
COPY --from=builder /app /app
```

**Konteyner içinde erişilebilen yerler:**
- `/app/modules/` → Tüm exploit/payload kodları
- `/root/.msf4/` → Oturum ve loot verileri (root çalışıyorsa)
- `/tmp/` → Geçici payload dosyaları
- Network namespace → Varsayılan bridge ağı üzerinden diğer konteynerler

### docker-compose.yml Analizi

```yaml
version: '3'
services:
  ms:
    environment:
      LHOST: 10.0.8.2        # Saldırgan IP adresi
    ports:
      - 4444:4444            # Varsayılan reverse shell portu
```

**Konteyner İçinde Açık Portlar:**

| Port | Servis | Risk |
|---|---|---|
| 4444 | Reverse TCP handler | Yüksek — varsayılan Meterpreter portu |
| 5555 | Alternatif handler | Orta |
| 8080 | HTTP handler | Orta |

### Güvenlik Açıkları

1. **Root ile çalışma riski:** `MSF_UID` ve `MSF_GID` environment variable ile kontrol edilir, ancak varsayılan değer root olabilir.

2. **Volume mount riskleri:** 
   ```bash
   docker run -v $(pwd):$(pwd) ...  # Host dosya sistemi erişimi
   ```
   Bu yapılandırma host sisteme erişimi açabilir.

3. **Ağ izolasyonu:** Varsayılan `docker-compose.yml`'de network izolasyonu tanımlanmamıştır. Tüm konteynerler aynı bridge ağını paylaşır.

4. **Kubernetes vs VM farkı:**
   - **VM:** Tam kernel izolasyonu, daha güçlü güvenlik sınırı
   - **Kubernetes:** Namespace izolasyonu, ancak shared kernel nedeniyle container escape riski
   - **Docker:** Lightweight izolasyon, en az güvenlik garantisi

**Güvenlik Önerisi:** Production/lab ortamında Metasploit'i `--cap-drop=ALL` ve `--security-opt=no-new-privileges` bayraklarıyla çalıştırın.

---

## Adım 5: Kaynak Kod ve Akış Analizi (Threat Modeling)

**Kapsam:** `msfconsole`, `lib/msf/core/`, `modules/`, `lib/msf/core/exploit/`, kimlik doğrulama mekanizmaları

### Uygulama Başlangıç Noktası (Entry Point)

```
msfconsole (CLI binary)
     ↓
lib/msf/ui/console.rb        → Konsol UI katmanı
     ↓
lib/msf/core/framework.rb    → Ana framework başlatıcı
     ↓
lib/msf/core/module_manager/ → Modül yöneticisi
     ↓
modules/exploits/            → Exploit modülleri
modules/auxiliary/           → Yardımcı modüller
modules/post/                → Post-exploitation modülleri
modules/payloads/            → Payload'lar (Meterpreter vb.)
```

### JWT Token Güvenliği (Senaryo: JWT İmza — None Algorithm)

Metasploit RPC API'si token tabanlı kimlik doğrulama kullanır. Eğer bu token JWT formatında işleniyorsa **"None Algorithm"** saldırısı kritik bir risk oluşturur:

```
Normal JWT:  header.payload.signature
             {"alg":"HS256"} → imza doğrulanır

Saldırı:     header.payload.
             {"alg":"none"}  → imza kontrolü atlanır!
```

Metasploit RPC token'ı düz bir bearer token olsa da, `authlogic` tabanlı session mekanizması cookie'de session ID taşır. Bu session ID'nin tahmin edilebilir (sequential) üretilmesi durumunda **Session Fixation** saldırısı mümkündür.

### Path Traversal Riski (Senaryo: Path Traversal Zafiyeti)

Metasploit modül yükleyicisi `lib/msf/core/module_manager/` dizin üzerinden `.rb` dosyaları yükler. Kötü niyetli bir modül yükleme isteğinde path traversal deneme vektörü:

```ruby
# Saldırı girişimi örneği:
use ../../../../etc/passwd
load /path/to/malicious/../../../etc/shadow
```

Metasploit bu riski `File.realpath` ve whitelist kontrolüyle önler, ancak özel modül dizinleri (`~/.msf4/modules/`) bu kontrolü bypass edebilir.

### Kimlik Doğrulama (Authentication) Mekanizması

Metasploit'in RPC API'si (`msfrpcd`) üç kimlik doğrulama yöntemi sunar:

1. **Token tabanlı kimlik doğrulama:**
   ```
   POST /api/1.0/auth/login
   → Token alınır
   → Her istekte Authorization header'a eklenir
   ```

2. **SSL/TLS:** RPC iletişimi varsayılan olarak SSL üzerinden yapılır
3. **Session tabanlı:** `authlogic` gem'i ile oturum yönetimi

**Kimlik doğrulama bypass vektörleri:**
- Token'ın güvensiz saklanması (log dosyalarına yazılması)
- Zayıf SSL yapılandırması (self-signed sertifika)
- Default credential kullanımı (`msf:msf`)

### Threat Model — STRIDE Analizi

| Tehdit Kategorisi | Senaryo | Etki | Önlem |
|---|---|---|---|
| **Spoofing** | Sahte Metasploit RPC sunucusu | Yüksek | SSL sertifika doğrulama |
| **Tampering** | Modül dosyalarının değiştirilmesi | Kritik | İmza doğrulaması / file integrity |
| **Repudiation** | Exploit loglarının silinmesi | Orta | Immutable logging |
| **Information Disclosure** | `~/.msf4/` dizininin okunması | Yüksek | Dosya izinleri (chmod 700) |
| **Denial of Service** | Modül önbelleğinin şişirilmesi | Düşük | Resource limiting |
| **Elevation of Privilege** | Root olmadan root erişimi | Kritik | Capability dropping |

### Kritik Soru Analizi

**"Bir hacker bu reponun kaynak kodunu incelersen ne tür bir varlığı (asset) çalabilir? Buluğunsuz auth mekanizmasına dışarıdan nasıl sızabilir?"**

**Çalınabilecek Varlıklar:**
1. `~/.msf4/db` → Tüm hedef sistemlerin IP, kimlik bilgileri, zafiyet geçmişi
2. `~/.msf4/loot/` → Ele geçirilmiş dosyalar ve credential'lar
3. `msfrpcd` token'ları → Tüm RPC oturumlarına erişim
4. `~/.msf4/.msf4_history` → Geçmiş komutlar (hedef IP'ler, kullanılan exploit'ler)

**Dışarıdan Sızma Vektörleri:**
1. **Default credentials:** `msfrpcd -P msf` ile başlatılan servise `msf:msf` ile giriş
2. **Açık port taraması:** Port 55553 (varsayılan RPC portu) internette açıksa
3. **SSRF:** Web arayüzü üzerinden iç ağ RPC servisine yönlendirme
4. **Gem zehirlenmesi (Supply Chain):** `Gemfile.lock` bypass edilerek zararlı gem sürümü yüklenmesi

---

## Genel Güvenlik Özeti

| Bileşen | Risk Seviyesi | Açıklama |
|---|---|---|
| Kurulum scripti | 🔴 Yüksek | curl-pipe-bash, imza doğrulaması yok |
| Bağımlılık yönetimi | 🟡 Orta | Gemfile.lock koruma sağlıyor, bazı gem'ler pinned |
| Docker izolasyonu | 🟡 Orta | Volume mount ve network izolasyonu eksik |
| CI/CD pipeline | 🟢 Düşük | Kapsamlı test ve lint süreci mevcut |
| RPC kimlik doğrulama | 🔴 Yüksek | Default credentials, açık port riski |
| Veri izolasyonu | 🔴 Yüksek | ~/.msf4/ hassas veri birikimi |

---

## Sonuç

Metasploit Framework, tasarım gereği ofansif güvenlik aracı olduğundan saldırı vektörlerini barındıran bir mimariyle gelir. Güvenli kullanım için: izole VM/Docker ortamında çalıştırılması, varsayılan credential'ların değiştirilmesi, oturum sonrası `~/.msf4/` temizliğinin yapılması ve RPC portlarının internete kapalı tutulması zorunludur.
