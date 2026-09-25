'use strict';
(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const base = '/assets/media/';
  const works = [
    {id:'forest', title:'The quiet between the trees.', category:'Natural worlds', file:'forest-light.webp', film:'When the light returns', description:'A study in soft light, moss and the small spaces between things. An imagined forest, made for looking a little longer.'},
    {id:'space', title:'A conversation with the sun.', category:'Spaces & forms', file:'quiet-architecture.webp', film:'Architecture of quiet', description:'A courtyard composed of warm stone and long shadows. An imaginary place where light becomes another building material.'},
    {id:'coast', title:'At the edge of everything.', category:'Natural worlds', file:'volcanic-coast.webp', film:'The shape of distance', description:'Dark sand, copper mountains and a line of white water. A digital landscape about scale, distance and the pleasure of an open horizon.'}
  ];
  const tracks = [
    {title:'Low tide', file:'low-tide.mp3', art:'coast'},
    {title:'Canopy', file:'canopy.mp3', art:'forest'},
    {title:'Warm concrete', file:'warm-concrete.mp3', art:'space'}
  ];
  const articles = {
    attention: {label:'OBSERVATIONS / 2 MIN READ', title:'The art of paying attention.', image:'forest', deck:'What changes when we stop collecting moments and start inhabiting them?', paragraphs:[
      'There is a particular kind of looking that asks nothing of the thing being seen. It does not need a name, a location or a photograph to take home. It is simply a willingness to remain. A patch of moss can hold this kind of attention as easily as a mountain. The difference is often the time we give it.',
      'In our forest study, the first thing you may notice is the beam of light. It offers an obvious route through the frame: a bright interruption in a world of greens. But stay a little longer and the picture begins to rearrange itself. The dark trunk becomes a border. The ground becomes a collection of separate textures. The brightest part is no longer the only part worth seeing.',
      'An image is useful here because it waits. Unlike a passing view from a train, it does not disappear while you decide what matters. You can move back to a corner you overlooked. You can let your eyes wander without worrying about the moment ending. There is no correct sequence and nothing to complete.',
      'Try choosing a small area at the edge of the frame. Look for three tones rather than three objects. Find a line that continues behind something else. Notice where a clear shape becomes difficult to describe. These are not exercises in expertise. They are ways of giving an ordinary act a little more room.',
      'The landscapes in this atlas are imagined, composed with generative tools and selected for their atmosphere. They are not records of a journey. That makes the invitation a little different: not to imagine where we went, but to notice what an arrangement of light and texture makes possible in your own attention.',
      'Perhaps you will leave with a detail. Perhaps only with the sense that the frame was larger than it first appeared. Either is enough. The point of looking longer is not to extract more from an image. Sometimes it is simply to become less hurried in its company.'
    ]},
    sound: {label:'SOUND NOTES / 2 MIN READ', title:'A room made of sound.', image:'coast', deck:'On repetition, gentle textures and music that leaves something unsaid.', paragraphs:[
      'Some music seems to stand directly in front of us. Other music opens a door and allows us to find our own place inside. The pieces in our listening room began with the second possibility: a few tones, a slow change, enough space for a thought to arrive without being interrupted.',
      'Low tide starts from a simple harmonic shape. Its notes return, but they do not arrive with precisely the same weight. A higher tone appears at the edge of the chord. A quieter note follows later. The interest is in these small shifts rather than a dramatic destination. Nothing is trying to win the room.',
      'Repetition is sometimes mistaken for stillness. Listen to a repeated phrase and you may find that the phrase seems to change because your attention changes around it. One pass brings forward the low note; the next makes a small high tone newly visible. The sequence provides a place to return to, while the act of listening does the travelling.',
      'These are original synthetic compositions. There is no borrowed recording of a shore or a forest underneath them, and no claim to reproduce the sound of a particular place. Their connection to the images is more oblique: a shared pace, a softness at the edge, a preference for leaving some of the frame empty.',
      'Try a low volume first. Let the piece share the room with the noises already there: a chair moving, a passing car, the small sounds of making a cup of tea. Headphones offer a different kind of closeness, revealing the gentle separation between notes. Neither way is more correct. A room has more than one seat.',
      'Each piece is only a little over a minute. You may replay it, move to another, or stop before it ends. The player is an invitation rather than a schedule. Sometimes the most useful thing a piece of music can do is give the silence after it a slightly different shape.'
    ]},
    light: {label:'FORM & FEELING / 2 MIN READ', title:'The other half of a building.', image:'space', deck:'A wall is one thing. The light that touches it is another.', paragraphs:[
      'Draw a simple courtyard and it may appear complete: four sides, an opening, perhaps a stair. But introduce a low sun and another architecture appears. A doorway projects itself across the ground. A flat wall seems folded by a diagonal. An empty corner acquires a weight it did not have a moment before.',
      'Our courtyard is an imagined space, assembled around a small conversation between solid forms and passing light. The stone remains warm even in shadow. The opening in the wall offers a view of another surface rather than an explanation of the whole building. The stairs suggest movement, though nobody is present to make it.',
      'What draws us to the scene is not the possibility of solving its plan. It is the way one shape lends meaning to another. The curved opening makes the straight stair feel more deliberate. The still pool makes the dry stone feel more tactile. Each element gives the eye a different pace.',
      'A shadow can be read as an absence, but it also behaves like an object. It has an edge, a direction and a relationship to its neighbours. In the courtyard it is often the darkest shape that holds the composition together. Remove it in your imagination and the scene becomes less legible, even though more of the surface is now visible.',
      'The motion study moves gently into this arrangement. The camera does not reveal a secret room or a new destination. It simply changes the proportion of what is already there. A small movement is enough to make the arch feel larger and the outer wall a little more distant. The interest lies in measure, not surprise.',
      'You do not need a remarkable building to continue this kind of looking. A window, a folded curtain or a square of afternoon light can offer the same small exchange. The material supplies a surface; the light makes a temporary drawing. Tomorrow it will begin again with a different line.'
    ]}
  };
  const read = (key, fallback) => { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } };
  const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
  const initialSaved = read('3xi.saved', []);
  const saved = new Set(Array.isArray(initialSaved) ? initialSaved.filter(id => works.some(w => w.id === id)) : []);
  let toastTimer, galleryIndex = 0, trackIndex = 0, loadedTrack = -1;
  const audio = $('#ambient-audio'), video = $('#film-player');
  const work = id => works.find(item => item.id === id);
  function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 2800); }
  function openDialog(dialog) { $$('dialog[open]').forEach(d => d.close()); dialog.showModal(); }
  $$('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  $$('dialog').forEach(dialog => dialog.addEventListener('click', event => { if(event.target !== dialog) return; const b = dialog.getBoundingClientRect(); if(event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom) dialog.close(); }));
  function showGallery(id) {
    const item = work(id); if(!item) return;
    galleryIndex = works.indexOf(item);
    $('#gallery-image').src = base + item.file; $('#gallery-image').alt = item.description;
    $('#gallery-category').textContent = item.category; $('#gallery-title').textContent = item.title;
    $('#gallery-description').textContent = item.description; $('#gallery-position').textContent = `${galleryIndex + 1} / ${works.length}`;
    if(!$('#gallery-dialog').open) openDialog($('#gallery-dialog'));
  }
  function stepGallery(step) { showGallery(works[(galleryIndex + step + works.length) % works.length].id); }
  $$('[data-gallery]').forEach(b => b.addEventListener('click', () => showGallery(b.dataset.gallery)));
  $('#gallery-prev').addEventListener('click', () => stepGallery(-1)); $('#gallery-next').addEventListener('click', () => stepGallery(1));
  $('#gallery-dialog').addEventListener('keydown', e => { if(e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); stepGallery(e.key === 'ArrowLeft' ? -1 : 1); } });
  function syncSaved() {
    $$('[data-save]').forEach(b => { const item = work(b.dataset.save), selected = saved.has(item.id); b.setAttribute('aria-pressed', String(selected)); b.setAttribute('aria-label', `${selected ? 'Unsave' : 'Save'} ${item.title}`); });
    $('#saved-count').hidden = !saved.size; $('#saved-count').textContent = saved.size;
    const container = $('#saved-items'); container.replaceChildren();
    if(!saved.size) { const p = document.createElement('p'); p.className = 'saved-empty'; p.textContent = 'Your atlas is waiting. Tap the bookmark on an image to keep it here.'; container.append(p); return; }
    for(const id of saved) {
      const item = work(id), row = document.createElement('div'); row.className = 'saved-item';
      row.innerHTML = `<button aria-label="View saved image"><img alt="" src="${base + item.file}"></button><div><h3><button>${item.title}</button></h3><p>${item.category}</p></div><button aria-label="Remove saved image"><svg class="icon"><use href="#i-close"/></svg></button>`;
      row.querySelector('button').addEventListener('click', () => showGallery(id)); row.querySelector('h3 button').addEventListener('click', () => showGallery(id)); row.lastElementChild.addEventListener('click', () => toggleSaved(id)); container.append(row);
    }
  }
  function toggleSaved(id) { if(!work(id)) return; saved.has(id) ? saved.delete(id) : saved.add(id); const persisted = write('3xi.saved', [...saved]); syncSaved(); toast(persisted ? (saved.has(id) ? 'Added to your little atlas.' : 'Removed from your collection.') : 'Saved for this visit. Browser storage is unavailable.'); }
  $$('[data-save]').forEach(b => b.addEventListener('click', () => toggleSaved(b.dataset.save)));
  $('#open-saved').addEventListener('click', () => { syncSaved(); openDialog($('#saved-dialog')); }); syncSaved();
  $$('.filter').forEach(button => button.addEventListener('click', () => {
    const category = button.dataset.filter; let count = 0;
    $$('.filter').forEach(b => { const on = b === button; b.classList.toggle('active', on); b.setAttribute('aria-pressed', String(on)); });
    $$('.collection-card').forEach(card => { card.hidden = category !== 'all' && card.dataset.category !== category; if(!card.hidden) count++; });
    $('#collection-grid').classList.toggle('filtered', category !== 'all'); $('#collection-count').textContent = `${count} SELECTED ${count === 1 ? 'WORK' : 'WORKS'}`;
  }));
  async function playFilm(id) {
    const item = work(id); if(!item) return;
    audio.pause(); $('#film-title').textContent = item.film; video.poster = base + item.file; video.src = base + id + '.mp4';
    openDialog($('#film-dialog')); video.load();
    try { await video.play(); } catch { if($('#film-dialog').open) toast('Press play in the film to begin.'); }
  }
  $$('[data-film]').forEach(b => b.addEventListener('click', () => playFilm(b.dataset.film)));
  $('#film-dialog').addEventListener('close', () => { video.pause(); video.removeAttribute('src'); video.load(); });
  video.addEventListener('error', () => { if(video.getAttribute('src')) toast('The film could not load. Please try again.'); });
  const time = value => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2,'0')}`;
  const storedVolume = read('3xi.volume', .6); audio.volume = typeof storedVolume === 'number' && Number.isFinite(storedVolume) ? Math.min(1, Math.max(0, storedVolume)) : .6;
  $('#audio-volume').value = audio.volume;
  function syncPlayback() {
    const playing = !audio.paused && !audio.ended;
    $('#audio-toggle-icon').setAttribute('href', playing ? '#i-pause' : '#i-play'); $('#audio-toggle').setAttribute('aria-label', playing ? 'Pause music' : 'Play music'); document.body.classList.toggle('is-playing', playing);
    $$('[data-track]').forEach(b => { const current = Number(b.dataset.track) === trackIndex; b.classList.toggle('active', current && loadedTrack !== -1); b.querySelector('use').setAttribute('href', current && playing ? '#i-pause' : '#i-play'); b.setAttribute('aria-label', `${current && playing ? 'Pause' : 'Play'} ${tracks[Number(b.dataset.track)].title}`); });
  }
  function selectTrack(index) {
    trackIndex = (index + tracks.length) % tracks.length; const item = tracks[trackIndex];
    $('#dock-title').textContent = item.title; $('#dock-cover').src = base + work(item.art).file;
    if(loadedTrack !== trackIndex) { audio.src = base + item.file; loadedTrack = trackIndex; audio.load(); $('#audio-current').textContent = '0:00'; $('#audio-seek').value = 0; }
    syncPlayback();
  }
  async function playMusic() { if(loadedTrack !== trackIndex) selectTrack(trackIndex); if(!video.paused) video.pause(); try { await audio.play(); } catch { if(audio.getAttribute('src')) toast('Unable to play music. Check your connection and try again.'); } }
  $('#audio-toggle').addEventListener('click', () => audio.paused ? playMusic() : audio.pause());
  function stepTrack(step) { selectTrack(trackIndex + step); playMusic(); }
  $('#audio-prev').addEventListener('click', () => stepTrack(-1)); $('#audio-next').addEventListener('click', () => stepTrack(1));
  $$('[data-track]').forEach(b => b.addEventListener('click', () => { const index = Number(b.dataset.track); if(index === trackIndex && !audio.paused) audio.pause(); else { selectTrack(index); playMusic(); } }));
  ['play','pause','ended'].forEach(name => audio.addEventListener(name, syncPlayback));
  audio.addEventListener('ended', () => stepTrack(1));
  audio.addEventListener('loadedmetadata', () => { if(Number.isFinite(audio.duration)) { $('#audio-seek').max = audio.duration; $('#audio-duration').textContent = time(audio.duration); } });
  audio.addEventListener('timeupdate', () => { $('#audio-current').textContent = time(audio.currentTime); $('#audio-seek').value = audio.currentTime; });
  $('#audio-seek').addEventListener('input', e => { if(Number.isFinite(audio.duration)) audio.currentTime = Math.min(audio.duration, Number(e.target.value)); });
  $('#audio-volume').addEventListener('input', e => { audio.volume = Number(e.target.value); audio.muted = false; write('3xi.volume', audio.volume); });
  $('#audio-mute').addEventListener('click', () => { audio.muted = !audio.muted; });
  audio.addEventListener('volumechange', () => { const muted = audio.muted || !audio.volume; $('#audio-mute').setAttribute('aria-pressed', String(muted)); $('#audio-mute').setAttribute('aria-label', muted ? 'Unmute music' : 'Mute music'); });
  audio.addEventListener('error', () => { syncPlayback(); toast('The music could not load. Please try again.'); });
  function reading({label, title, image, deck, paragraphs}) {
    const node = $('#reading-content'); node.replaceChildren();
    const eyebrow = document.createElement('p'); eyebrow.className = 'eyebrow'; eyebrow.textContent = label;
    const heading = document.createElement('h2'); heading.id = 'reading-title'; heading.textContent = title;
    const intro = document.createElement('p'); intro.className = 'reading-deck'; intro.textContent = deck; node.append(eyebrow, heading, intro);
    if(image) { const img = document.createElement('img'); img.className = 'reading-hero'; img.src = base + work(image).file; img.alt = work(image).description; node.append(img); }
    const body = document.createElement('div'); body.className = 'article-body'; paragraphs.forEach(text => { const p = document.createElement('p'); p.textContent = text; body.append(p); }); node.append(body);
    const credit = document.createElement('p'); credit.className = 'reading-credit'; credit.textContent = '3xi Atlas · Independent visual journal · Volume 001'; node.append(credit); openDialog($('#reading-dialog')); $('#reading-dialog').scrollTop = 0;
  }
  $$('[data-article]').forEach(b => b.addEventListener('click', () => reading(articles[b.dataset.article])));
  const pages = {
    about: {label:'ABOUT THE ATLAS', title:'A place to wander.', deck:'An independent collection of images, moving pictures and original sound.', paragraphs:['3xi Atlas is a small digital journal about attention: the feeling of a landscape, the shape of a shadow, and the way a few notes can change the pace of a room. Volume 001 contains three visual studies, three short films and three original ambient tracks.', 'Our landscapes and architectural images were created with generative image tools. They depict imagined places, not documentary photographs of named locations. The films add gentle camera movement to these compositions and pair them with original synthetic music, composed for this collection.', 'Explore an image, read a note, or spend a minute in the listening room. The collection has no prescribed order. Bookmarks stay in this browser, and you can remove them whenever you like.']},
    privacy: {label:'A NOTE ON PRIVACY', title:'Your own pace. Your own space.', deck:'A small collection with simple browser preferences.', paragraphs:['This website has no account form or advertising tracker. Bookmarks, music volume and your motion preference are stored locally in your browser when browser storage is available. Clearing this site’s browser data removes those preferences.', 'Images, video and audio are served by this website. Opening a film or playing a track makes a request for that media file. No audio starts automatically on your first visit. After you start music, the playlist advances to the next track until you pause it.', 'The hosting server and its network provider may keep ordinary request logs, such as network addresses, response codes and request times. Browser preferences are not sent to an application backend by this website.']}
  };
  $$('[data-page]').forEach(b => b.addEventListener('click', () => reading(pages[b.dataset.page])));
  $('#surprise-me').addEventListener('click', () => showGallery(works[Math.floor(Math.random() * works.length)].id));
  const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
  let motion = read('3xi.motion', motionQuery.matches); if(typeof motion !== 'boolean') motion = motionQuery.matches;
  function syncMotion() { document.documentElement.classList.toggle('reduce-motion', motion); $('#motion-toggle').setAttribute('aria-pressed', String(motion)); $('#motion-toggle').textContent = motion ? 'Motion reduced' : 'Reduce motion'; }
  $('#motion-toggle').addEventListener('click', () => { motion = !motion; write('3xi.motion', motion); syncMotion(); }); syncMotion();
  function nav(open) { $('#main-nav').classList.toggle('open', open); $('#menu-toggle').setAttribute('aria-expanded', String(open)); $('#menu-toggle').setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation'); }
  $('#menu-toggle').addEventListener('click', () => nav($('#menu-toggle').getAttribute('aria-expanded') !== 'true'));
  $$('#main-nav a').forEach(a => a.addEventListener('click', () => nav(false))); document.addEventListener('keydown', e => { if(e.key === 'Escape') nav(false); });
  $('#year').textContent = new Date().getFullYear();
})();
