<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/custom_components/hikvision_virtual_indoor_station/brand/dark_logo@2x.png">
    <img src="https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/custom_components/hikvision_virtual_indoor_station/brand/icon@2x.png" alt="" width="256">
  </picture>
</p>

<h1 align="center">Hikvision Virtual Indoor Station</h1>

<p align="center">Home Assistant come posto interno del tuo citofono Hikvision: rispondi, parla e apri la porta dalle plance e dai telefoni</p>

<p align="center">
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/releases/latest"><img alt="Ultima versione" src="https://img.shields.io/github/v/release/webysther/ha-hikvision-virtual-indoor-station?include_prereleases&label=release&color=41BDF5"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img alt="Repository personalizzato del Marketplace" src="https://img.shields.io/badge/Marketplace-custom-41BDF5?logo=homeassistant&logoColor=white"></a>
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/actions/workflows/tests.yaml"><img alt="Test" src="https://github.com/webysther/ha-hikvision-virtual-indoor-station/actions/workflows/tests.yaml/badge.svg"></a>
  <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/LICENSE"><img alt="Licenza" src="https://img.shields.io/github/license/webysther/ha-hikvision-virtual-indoor-station?color=41BDF5"></a>
</p>

<p align="center"><a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/README.md">English</a> · <b>Italiano</b> · <a href="https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/README.pt-BR.md">Português (Brasil)</a></p>

Fai di Home Assistant il posto interno del tuo citofono video Hikvision. Il suo
pulsante suona in Home Assistant, sulle tue plance e sui telefoni: rispondi,
parli, riagganci o rifiuti la chiamata, e apri la porta.

> **Stato: in sviluppo.** Provato con un DS-KD8003-IME1(B), firmware V3.7.3.

## Perché questa integrazione

- **Tutto in uno.** Il server SIP che il citofono chiama, la scheda e una plancia
  disegnata come lo schermo di un posto interno arrivano con l'integrazione:
  nessun add-on, server SIP, broker MQTT o account cloud da configurare accanto.
- **Ibrida, il meglio di ogni protocollo.** SIP porta la chiamata, come il
  citofono si aspetta da un posto interno; RTP porta la tua voce alla porta, nei
  pacchetti che riproduce meglio, e riporta la voce del visitatore una volta
  risposto; RTSP porta l'immagine, e il suono mentre monitori; ISAPI apre le
  porte e parla dal suo altoparlante fuori da una chiamata.
- **Platinum dal primo giorno.** Segue tutte le regole del livello più alto della
  [scala di qualità delle integrazioni](https://www.home-assistant.io/docs/quality_scale/):
  asincrona, tipizzata, interamente testata, tradotta, con riparazioni, nuova
  autenticazione e diagnostica. Il protocollo vive in una libreria propria su
  PyPI, [aiohikvision](https://pypi.org/project/aiohikvision/).
- **Provata su hardware reale.** Ogni comportamento su cui si basa è stato
  misurato su un citofono vero (un DS-KD8003-IME1(B)), e su di esso le chiamate
  vengono risposte, rifiutate e chiuse.

## Funzionalità

- **Il campanello suona in Home Assistant.** La linea VoIP del citofono si
  registra in Home Assistant e lo chiama: il visitatore sente squillare, e
  l'evento del campanello scatta.
- **Rispondi, riaggancia o rifiuta** dai pulsanti, dalle automazioni o dalle
  schede; ogni comando porta l'id della sua chiamata, così un tocco in ritardo
  non tocca mai il visitatore successivo.
- **Parla con il visitatore.** Durante una chiamata il tuo microfono va alla
  porta con la chiamata; fuori da una chiamata, dall'altoparlante del citofono.
- **Vedi e senti il visitatore**: la telecamera del citofono, riprodotta con
  WebRTC, e la voce del visitatore dalla chiamata stessa una volta risposto, in
  ogni browser (anche un iPad).
- **Apri le porte** collegate al citofono, un pulsante per ciascuna.
- **Regola il citofono** da Home Assistant: l'immagine della sua telecamera, i
  suoi volumi, quanto resta aperta ogni porta e il suo messaggio vocale, entro
  gli intervalli che indica.
- **I tuoi telefoni suonano con la porta**: una notifica con la foto della
  porta, anche con le modalità full immersion, con **Rispondi**, **Apri porta** e
  **Rifiuta**.
- **Sa quando la porta non può chiamare**: un sensore della registrazione SIP, e
  una riparazione che spiega come puntare il citofono su Home Assistant.
- **Mostra quanto è carico**: la sua CPU e quanti client trasmettono il suo
  video, e a cosa è collegato ogni ingresso e ogni uscita.
- **Vedi quando arrivano le visite**: ogni visita è contata (risposta, persa,
  rifiutata), e due grafici mostrano le ore in cui suona la porta nelle ultime 8
  settimane e le visite di ciascuno degli ultimi 28 giorni.

## Casi d'uso

- Un tablet a parete o i telefoni di casa come posto interno, senza monitor
  Hikvision e senza account cloud.
- Una notifica con la foto del visitatore quando qualcuno suona, e la porta
  aperta da lì.
- Automazioni: una luce all'ingresso quando suona di notte, le chiamate
  rifiutate quando non c'è nessuno in casa, il cancello aperto per un visitatore
  conosciuto.

## Installazione

Dal [Marketplace](https://www.home-assistant.io/integrations/marketplace/) di
Home Assistant:

[![Apri Home Assistant e apri Hikvision Virtual Indoor Station nel Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=webysther&repository=ha-hikvision-virtual-indoor-station&category=integration)

1. Apri il link qui sopra, oppure **Impostazioni → Marketplace → Aggiungi da
   link**, e aggiungi
   `https://github.com/webysther/ha-hikvision-virtual-indoor-station`.
2. Apri **Hikvision Virtual Indoor Station** e installala.

Home Assistant 2026.10 o più recente.

## Configurazione

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Hikvision
Virtual Indoor Station**, poi:

| Campo | Cosa indicare |
| --- | --- |
| Host | L'indirizzo IP o il nome del citofono nella tua rete |
| Nome utente | Un account della sua pagina web (va bene il suo account admin) |
| Password | La password di quell'account |

Poi punta il citofono su Home Assistant, dalla sua pagina web:

1. **System and Maintenance → System Configuration → Network → Device Access →
   VoIP**, linea **VoIP1**:
   - attiva **Enable VoIP Gateway**;
   - **Server IP Address**: l'indirizzo di Home Assistant; **Server Port**:
     5060;
   - **Register User Name** e **Number**: un numero per il citofono, come `100`
     (Home Assistant non controlla la **Registration Password**);
   - **Display User Name**: un nome per il citofono;
   - **Expiry Time** può restare a 60 minuti: Home Assistant lo riduce a 10;
   - lascia **Enable P2P** spento.

   Dopo il salvataggio, **Registration Status** mostra **Registered**.

   ![La linea VoIP del citofono, registrata in Home Assistant](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/voip.png)

2. **Video Intercom → Call Parameters → Number Settings**: collega la stanza del
   pulsante di chiamata (stanza 1) alla linea SIP. Lo schermo del citofono ne
   mostra il nome durante le chiamate.

   ![La stanza 1 collegata alla linea SIP](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/number-settings.png)

3. **Video Intercom → Call Parameters → Call Priority**: **Telephone Gateway**
   come **Priority1**, così il pulsante chiama Home Assistant. Il suo **Ring
   Duration** è per quanto squilla una chiamata prima di essere persa.

   ![Telephone Gateway come prima priorità di chiamata](https://raw.githubusercontent.com/webysther/ha-hikvision-virtual-indoor-station/main/docs/images/call-priority.png)

4. Imposta l'audio SIP solo su G.711.

Il sensore **SIP registration** si accende quando il citofono si registra.
L'indirizzo, l'account e la password si possono cambiare in seguito con
**Riconfigura**.

Passo dopo passo, dal citofono alla plancia e ai telefoni:
[il tutorial](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/docs/tutorial.md) (in inglese).

## Plancia e scheda

L'integrazione porta la sua scheda e la sua plancia: non c'è nient'altro da
installare.

- **La plancia**: **Impostazioni → Plance → Aggiungi plancia → Hikvision Virtual
  Indoor Station**. Ha una vista per ogni citofono, con la sua scheda, la sua
  attività (squilli, chiamate, registrazione) e le sue visite: quando suona la
  porta (un orologio di 24 ore delle ultime 8 settimane), le visite di ciascuno
  degli ultimi 28 giorni (con i fine settimana in ombra) e quelle di ogni
  settimana dell'ultimo trimestre. Verde è risposta, ambra persa e rosso
  rifiutata, come i tasti della scheda.
- **La scheda**: **Hikvision Virtual Indoor Station** nella scelta delle schede
  di qualsiasi plancia, con un editor visuale. È disegnata come lo schermo di un
  posto interno:
  - la telecamera della porta, dal vivo mentre la porta suona, durante una
    chiamata o mentre monitori, e la sua foto per il resto del tempo; sopra, il
    nome del citofono e lo stato della chiamata, quando ce n'è una;
  - **Rispondi** e **Rifiuta** mentre la porta suona, **Riaggancia** dopo aver
    risposto, **Monitora** a riposo, e **Silenzia suoneria** per questo browser;
  - **Premi per parlare**: tienilo premuto (o la barra spaziatrice con il
    pulsante selezionato). La tua voce va con la chiamata, o dall'altoparlante
    della porta a riposo, e il suono della porta si spegne mentre parli;
  - a destra, sulla stessa riga, una chiave per ogni porta che si apre, e le tue
    scorciatoie.

```yaml
type: custom:hikvision-indoor-station-card
# Il citofono (il suo dispositivo); se manca, il primo
device_id: 0123456789abcdef0123456789abcdef
# hold (predefinito) o toggle: premi una volta per parlare, una per smettere
talk_mode: hold
# Altre entità: i pulsanti vengono premuti, le scene e gli script accesi,
# le automazioni avviate, il resto commutato
shortcuts:
  - light.porch
  - entity: scene.welcome
    name: Benvenuto
    icon: mdi:hand-wave
# false: i tasti mostrano solo le icone
show_name: true
# false: niente nome né stato della chiamata sopra la telecamera
show_state: true
# false: nasconde quel tasto
show_monitor: true
show_talk: true
show_ringer: true
# Tasti per riga (da 1 a 12), o righe di tasti (da 1 a 4); senza, una
# riga finché ci stanno. Un'ultima riga con meno tasti sta al centro
# columns: 3
# rows: 2
```

I browser trattengono il suono di una pagina finché non la si tocca: la scheda
chiede un tocco se la porta suona prima. Anche i telefoni riproducono il suono
della porta solo dopo un tocco: **Rispondi** e **Monitora** lo accendono, e quando
si risponde da una notifica la scheda chiede un tocco per sentire la porta.
Durante una chiamata la voce del visitatore arriva dalla chiamata, non dalla
telecamera: anche un browser il cui lettore della telecamera non ha il suono
G.711 (un iPad, che riproduce la telecamera con HLS) lo sente. Per parlare serve
Home Assistant aperto in HTTPS.

## App per dispositivi mobili

Ogni telefono o tablet con l'app di Home Assistant (**App per dispositivi mobili**,
come la chiama Home Assistant) può suonare con un citofono: **Impostazioni →
Dispositivi e servizi → Hikvision Virtual Indoor Station**, poi **Aggiungi app per
dispositivi mobili** sul citofono.

| Campo | Cosa fa |
| --- | --- |
| App per dispositivi mobili | Un dispositivo dell'app di Home Assistant (App per dispositivi mobili) |
| Non disturbare | L'app non viene avvisata quando suona questo citofono |
| Può aprire la porta | La notifica ha un pulsante che apre la porta |

Gli ultimi due si possono cambiare dopo (**Riconfigura** sull'app); aggiungere o
cambiare un'app non interrompe una chiamata. Quando la porta suona, ogni app
riceve una notifica con la foto della porta, consegnata
subito (time-sensitive su iOS, priorità alta su Android), con:

- **Rispondi**: apre il pannello del posto interno, una pagina con la scheda del
  citofono, che risponde a quella chiamata;
- **Apri porta**: apre la prima porta con una serratura, in background (un
  iPhone chiede di essere sbloccato prima);
- **Rifiuta**: il citofono mostra occupato.

I pulsanti funzionano solo finché dura la loro chiamata, e la notifica sparisce
quando la chiamata riceve risposta altrove, viene persa o finisce. Un tocco sulla
notifica apre il pannello senza rispondere. Un'app che lascia Home Assistant ha
una riparazione, che la rimuove dal citofono.

## Rimozione

**Impostazioni → Dispositivi e servizi → Hikvision Virtual Indoor Station**:
**Elimina**, nei tre puntini del citofono, lo rimuove con il suo dispositivo e le
sue entità. Poi punta la linea VoIP del citofono altrove (o disattivala), e
disinstalla l'integrazione dal Marketplace. Una sola app si rimuove con
**Elimina** nei tre puntini della sua riga, sotto il suo citofono. Le visite di
un citofono vengono dimenticate con lui.

## Come vengono aggiornati i dati

- **Le chiamate arrivano subito**: il citofono chiama Home Assistant via SIP, e
  il sensore della chiamata, l'evento del campanello e le schede cambiano
  all'istante.
- **Una volta al minuto** al citofono viene chiesto cosa comandano le sue
  uscite e quanto è carico (tre piccole richieste): le sue entità non sono
  disponibili finché non risponde, e una porta la cui uscita non comanda più una
  serratura non si apre più.
- **Ogni 5 minuti** vengono letti le sue impostazioni e i suoi ingressi: un
  citofono che trasmette il suo video ha la CPU alta, quindi ciò che cambia di
  rado viene letto meno spesso. Un'impostazione cambiata da Home Assistant viene
  riletta subito.
- **La registrazione**: il citofono si registra al massimo ogni 10 minuti, e
  manda un keepalive ogni 20 secondi mentre è registrato.
- **La telecamera** trasmette su richiesta; la sua foto viene scattata quando
  una plancia la chiede.
- **I telefoni** vengono avvisati quando la porta suona, e la notifica viene
  ritirata quando la chiamata riceve risposta altrove, viene persa o finisce.
- **Le visite** vengono contate alla fine di ogni chiamata, e quelle delle ultime
  8 settimane sono conservate in Home Assistant (quando ha suonato la porta e
  come è finita la chiamata, niente su chi ha suonato). I grafici vengono
  disegnati quando una plancia li mostra.

## Limitazioni note

- **Un server SIP, porta 5060.** Non può funzionare accanto a un altro server SIP
  sulla stessa porta, come l'integrazione Voice over IP.
- **Solo G.711.** L'Opus e il G.722.1 dei citofoni non sono standard.
- **Il tempo di conversazione del citofono** chiude la chiamata (90 secondi per
  impostazione predefinita): aumentalo dalla sua pagina web.
- **Half duplex.** Il cancellatore d'eco del citofono abbassa la voce del
  visitatore mentre parli: parlate a turno.
- **Per parlare serve HTTPS** nel browser (per il microfono).
- **Tre pulsanti su Android**: una notifica apre solo la prima porta con una
  serratura.
- **Le notifiche richiedono il telefono online**: passano dal servizio push
  dell'app di Home Assistant, che limita quante un telefono ne riceve al giorno.

## Risoluzione dei problemi

- **Il pulsante non suona.** Controlla il sensore **SIP registration**. Spento:
  la linea VoIP non punta su Home Assistant (vedi Configurazione), oppure la
  porta 5060 è bloccata tra i due. Una riparazione indica l'indirizzo e la porta
  da impostare.
- **La configurazione viene ritentata, dicendo che la porta 5060 è occupata.**
  Un altro server SIP la sta usando: fermalo, oppure ferma l'integrazione Voice
  over IP.
- **Il citofono emette tre bip e non mostra nulla.** Nessun server SIP ha
  risposto: Home Assistant era spento o irraggiungibile.
- **Nessun suono alla porta, o un suono a scatti.** Imposta l'audio SIP del
  citofono solo su G.711.
- **La chiamata si chiude da sola dopo 90 secondi.** È il tempo di conversazione
  del citofono.
- **Il pulsante della porta 2 non è disponibile.** La sua uscita comanda un
  campanello o niente (vedi il suo sensore **Output**): impostala su Electric
  Lock nella pagina web del citofono (Access Control → I/O Settings).
- **Un telefono non suona.** Consenti le notifiche dell'app di Home Assistant sul
  telefono, e controlla che non sia in **Non disturbare** per questo citofono. La
  sua app deve aver fatto l'accesso: Home Assistant ha allora la sua azione di
  notifica (`notify.mobile_app_<il suo nome>`).
- **Il video tarda a partire.** Attiva **Precaricare il flusso della
  telecamera** nelle impostazioni della telecamera del citofono: il suo flusso è
  allora sempre pronto (tiene aperto un flusso del citofono).
- **Il video rallenta o si blocca.** Guarda **Video sessions** e **CPU usage**:
  ogni client che trasmette il citofono (Home Assistant, un registratore, l'app
  Hik-Connect) lo carica, e con la CPU vicina al 90% il video rallenta.
  Trasmettilo da meno posti, o riproduci la sua telecamera **Flusso secondario**
  (attivala prima): un'immagine più piccola, più leggera per il citofono e per il
  telefono.

Prima di aprire una issue, attiva i log di debug (**Impostazioni → Dispositivi e
servizi → Hikvision Virtual Indoor Station → Abilita la registrazione di debug**),
ricarica l'integrazione, ripeti ciò che non va e disattivali: Home Assistant scarica
il log. È breve e dice una volta ciò che serve a una correzione: come è stato
riconosciuto il citofono (modello, firmware, cosa sa fare, i comportamenti impostati
per il suo modello), cosa è stato configurato (porte, ingressi, uscite,
altoparlante, telecamere, SIP), i suoi flussi e ogni richiesta che fallisce. Allegalo
con la diagnostica (**Scarica diagnostica** nella pagina del dispositivo): contiene il
rapporto del citofono, letto senza cambiare nulla e senza indirizzi, nomi né account.

## Dispositivi supportati

Citofoni video Hikvision con SIP standard (una linea VoIP), come la serie
DS-KD8003 con firmware V3.7.1 build250709 o più recente. Provato:
DS-KD8003-IME1(B) con V3.7.3. Altri citofoni delle serie DS-KD e DS-KV dovrebbero
funzionare; segnala il tuo.

## Entità

| Entità | Cosa fa |
| --- | --- |
| Telecamera | L'immagine e il suono della porta (RTSP), e le foto: il flusso principale |
| Flusso secondario (telecamera, disattivata di default) | Lo stesso, più leggero da riprodurre (720p su un DS-KD8003); una telecamera per ogni altro flusso del citofono |
| Doorbell (evento) | `ring`, `answered`, `rejected`, `missed`, `ended`, con l'id della chiamata |
| Call (sensore) | `idle`, `ringing`, `answered` |
| SIP registration (diagnostica) | Acceso finché il citofono può chiamare Home Assistant |
| Open door (pulsante) | Uno per porta, numerati quando sono più di una; non disponibile finché la sua uscita non comanda una serratura |
| Output (diagnostica) | Cosa comanda un'uscita configurabile: `electric_lock`, `doorbell`, `disabled` |
| Input (diagnostica) | A cosa è collegato un ingresso configurabile: `door_contact`, `exit_button`, `disabled` |
| CPU usage, Video sessions (diagnostica) | Quanto è carico il citofono: la sua CPU, e quanti client trasmettono il suo video |
| Visits, Missed visits (sensori) | Quante visite sono arrivate, e quante perse: contatori le cui statistiche danno le visite di ogni giorno, settimana o mese |
| Visits by hour, Visits by day (immagini) | Grafici: quando suona la porta (24 ore, le ultime 8 settimane), e le visite di ciascuno degli ultimi 28 giorni; verde risposta, ambra persa, rosso rifiutata |
| Answer, Hang up, Reject (pulsanti) | Agiscono sulla chiamata in corso |
| Microphone volume, Speaker volume, Call volume (configurazione) | I volumi del citofono |
| Door open time (configurazione) | Quanto resta aperta una porta, in secondi; una per porta |
| Voice prompt when a door opens, Door voice prompt (configurazione) | Se il citofono parla quando si apre una porta, e cosa dice: `long`, `short`, `doorisopen` |
| Day/night mode, Brightness, Contrast, Saturation, Sharpness, WDR (configurazione) | L'immagine della telecamera |

Le impostazioni compaiono quando il citofono le offre, con i suoi intervalli e
le sue scelte. Ci sono anche Day/night sensitivity, WDR level, Backlight
compensation, la sua area e Power line frequency, disattivate per impostazione
predefinita.

I nomi delle entità seguono la lingua di Home Assistant.

## Esempi di automazione

Una notifica quando qualcuno suona (ogni evento cambia lo stato del campanello,
anche due squilli di fila):

```yaml
triggers:
  - trigger: state
    entity_id: event.door_station_doorbell
    not_from: [unavailable, unknown]
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.event_type == 'ring' }}"
actions:
  - action: notify.notify
    data:
      title: C'è qualcuno alla porta
      message: "{{ now().strftime('%H:%M') }}"
```

Rifiutare le chiamate quando non c'è nessuno in casa:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.door_station_call
    to: ringing
conditions:
  - condition: state
    entity_id: zone.home
    state: "0"
actions:
  - action: button.press
    target:
      entity_id: button.door_station_reject
```

## Contribuire

Vedi [AGENTS.md](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/AGENTS.md)
(in inglese): come è organizzata l'integrazione, i suoi controlli e le sue
convenzioni. Il protocollo vive in
[aiohikvision](https://github.com/webysther/aio-hikvision).

## Progetti correlati

Altri progetti che portano i dispositivi Hikvision in Home Assistant. Se ne usi
uno per un citofono, prova questa integrazione: fa il posto interno in
un'integrazione sola, in locale, senza add-on, broker MQTT o account cloud. Per
telecamere e videoregistratori, prova
[Hikvision Bridge](https://github.com/yannik2480/hikvision_bridge), che si può
installare accanto a questa integrazione.

Citofoni e videocitofoni:

- [Hikvision Bridge](https://github.com/yannik2480/hikvision_bridge):
  telecamere, videoregistratori e citofoni via ISAPI locale (eventi, dirette,
  registrazioni, porte). Il codice ISAPI di
  [aiohikvision](https://github.com/webysther/aio-hikvision) viene da qui.
- [Hikvision-Addons](https://github.com/pergolafabio/Hikvision-Addons): un
  add-on costruito sull'SDK di Hikvision che espone il campanello via MQTT, per
  rispondere, rifiutare e chiudere le chiamate e aprire le porte.
- [SIP Indoor Station](https://github.com/arturzx/sip-indoor-station): un server
  SIP e un ponte audio WebRTC per i citofoni SIP, con la sua
  [integrazione](https://github.com/arturzx/sip-indoor-station-integration), la
  sua [scheda](https://github.com/arturzx/sip-indoor-station-card) e il suo
  [add-on](https://github.com/arturzx/hass-addons) in repository separati.
- [Hikvision Doorbell Integration](https://github.com/acardace/hikvision-doorbell-integration):
  audio bidirezionale WebRTC via ISAPI, con il suo
  [server](https://github.com/acardace/hikvision-doorbell-server).
- [Hikvision Intercom](https://github.com/schmidt-gabriel/hikvision-intercom-hass-integration):
  rilevamento del campanello e porte via ISAPI.
- [Hikvision Intercom (2 fili)](https://github.com/TimLuist1/hikvision-intercom):
  videocitofoni a 2 fili tramite l'SDK di Hikvision.
- [Hik-Connect](https://github.com/tomasbedrich/home-assistant-hikconnect):
  campanelli smart tramite il cloud Hik-Connect.
- [Intercom HomeKit](https://github.com/DmytryS/intercom-homekit): un add-on che
  fa del citofono un campanello video di Apple HomeKit.

Telecamere e videoregistratori:

- [Hikvision](https://www.home-assistant.io/integrations/hikvision/),
  l'integrazione inclusa in Home Assistant, basata su
  [pyHik](https://github.com/mezz64/pyHik).
- [Hikvision NVR / IP cameras](https://github.com/maciej-or/hikvision_next)
  (`hikvision_next`).

## Licenza

Il codice è sotto la
[Licenza MIT](https://github.com/webysther/ha-hikvision-virtual-indoor-station/blob/main/LICENSE).

Hikvision e Home Assistant sono marchi dei rispettivi proprietari, citati qui
solo per identificarli, senza implicarne l'approvazione; questo progetto non è
affiliato a Hikvision. L'icona dell'integrazione è un'opera originale.
