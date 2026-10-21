// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {createDialog} from '../../static/shared/dialog.mjs';

function fixture() {
  const {window} = new JSDOM('<button id="trigger">Open</button><button id="fallback">Fallback</button><dialog><input autofocus><button data-dialog-close><span>Cancel</span></button></dialog>');
  const document = window.document;
  const dialog = document.querySelector('dialog');
  const trigger = document.querySelector('#trigger');
  const fallback = document.querySelector('#fallback');
  // jsdom does not implement modal focus/inert; real Chromium tests do.
  dialog.showModal = () => {dialog.open = true; dialog.querySelector('input').focus();};
  dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new window.Event('close'));};
  return {window, dialog, trigger, fallback};
}

test('dialog opens once, preserves invoker and closes through nested dismiss control', () => {
  const {window, dialog, trigger} = fixture();
  const controller = createDialog(dialog);
  trigger.focus();
  controller.open();
  assert(dialog.open);
  assert.equal(window.document.activeElement, dialog.querySelector('input'));
  controller.open(dialog.querySelector('input'));
  dialog.querySelector('input').click();
  assert(dialog.open);
  dialog.dispatchEvent(new window.Event('close'));
  assert.equal(window.document.activeElement, dialog.querySelector('input'), 'stale queued close cannot steal modal focus');
  dialog.querySelector('span').click();
  assert(!dialog.open);
  assert.equal(window.document.activeElement, trigger);
  controller.close();
  controller.destroy();
  window.close();
});

test('dialog restores fallback when invoker is disabled or removed', () => {
  for (const removed of [false, true]) {
    const {window, dialog, trigger, fallback} = fixture();
    const controller = createDialog(dialog, {fallbackFocus: fallback});
    controller.open(trigger);
    if (removed) trigger.remove(); else trigger.disabled = true;
    controller.close();
    assert.equal(window.document.activeElement, fallback);
    controller.destroy();
    window.close();
  }
});

test('closed dialog teardown does not steal focus; external native close restores it', () => {
  const {window, dialog, trigger, fallback} = fixture();
  const controller = createDialog(dialog, {fallbackFocus: fallback});
  controller.open(trigger);
  dialog.close();
  assert.equal(window.document.activeElement, trigger);
  controller.destroy();
  assert.equal(window.document.activeElement, trigger);
  window.close();
});

test('dialog teardown closes modal and removes listeners; missing focus target is safe', () => {
  const {window, dialog, trigger} = fixture();
  const controller = createDialog(dialog);
  controller.open(null);
  controller.close();
  controller.open(trigger);
  controller.destroy();
  assert(!dialog.open);
  assert.equal(window.document.activeElement, trigger);
  dialog.showModal();
  dialog.querySelector('span').click();
  assert(dialog.open, 'teardown removed delegated listener');
  window.close();
});

test('dialog wraps Tab edges and ignores disabled, hidden and non-tabbable fields', () => {
  const {window, dialog, trigger} = fixture();
  dialog.insertAdjacentHTML('beforeend', '<input disabled><input tabindex="-1"><input hidden><div inert><button>Inert</button></div><input id="unrendered"><div hidden><button>Hidden ancestor</button></div>');
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => node.id === 'unrendered' ? [] : [{}];
  const controller = createDialog(dialog);
  controller.open(trigger);
  const input = dialog.querySelector('input');
  const button = dialog.querySelector('button');
  function press(key, shiftKey = false) {
    const event = new window.KeyboardEvent('keydown', {key, shiftKey, bubbles: true, cancelable: true});
    window.document.activeElement.dispatchEvent(event);
    return event.defaultPrevented;
  }
  assert.equal(press('ArrowDown'), false);
  assert.equal(press('Tab'), false);
  assert(press('Tab', true));
  assert.equal(window.document.activeElement, button);
  assert.equal(press('Tab', true), false);
  assert(press('Tab'));
  assert.equal(window.document.activeElement, input);
  dialog.querySelectorAll('input, button').forEach(node => {node.disabled = true;});
  const emptyTab = new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true});
  dialog.dispatchEvent(emptyTab);
  assert(emptyTab.defaultPrevented);
  controller.destroy();
  window.close();
});

test('nested dialog events do not dismiss or move focus in the parent', () => {
  const {window, dialog, trigger} = fixture();
  const controller = createDialog(dialog);
  dialog.insertAdjacentHTML('beforeend', '<dialog open><button data-dialog-close>Inner cancel</button></dialog>');
  const childButton = dialog.querySelector('dialog').querySelector('button');
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
  controller.open(trigger);
  childButton.focus();
  childButton.click();
  assert(dialog.open);
  const event = new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true});
  childButton.dispatchEvent(event);
  assert.equal(event.defaultPrevented, false);
  dialog.querySelector('input').focus();
  dialog.querySelector('input').dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true}));
  assert.equal(window.document.activeElement, dialog.querySelector(':scope > button'));
  controller.destroy();
  window.close();
});

test('reverse Tab from an autofocus heading wraps to the last control', () => {
  const {window, dialog, trigger} = fixture();
  dialog.insertAdjacentHTML('afterbegin', '<h2 tabindex="-1" autofocus>Review</h2>');
  dialog.querySelector('input').removeAttribute('autofocus');
  const heading = dialog.querySelector('h2');
  dialog.showModal = () => {dialog.open = true; heading.focus();};
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
  const controller = createDialog(dialog);
  controller.open(trigger);
  assert.equal(window.document.activeElement, heading);
  const reverse = new window.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true});
  heading.dispatchEvent(reverse);
  assert(reverse.defaultPrevented);
  assert.equal(window.document.activeElement, dialog.querySelector('button'));
  controller.close();
  assert.equal(window.document.activeElement, trigger);
  controller.destroy();
  window.close();
});

test('radio group edges use the checked radio and preserve independent groups', () => {
  const {window, dialog, trigger} = fixture();
  dialog.insertAdjacentHTML('beforeend', '<input type="radio" name="choice" checked id="checked"><input type="radio" name="choice" id="unchecked">');
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
  const controller = createDialog(dialog);
  controller.open(trigger);
  const checked = dialog.querySelector('#checked');
  checked.focus();
  function tab(shiftKey = false) {
    const event = new window.KeyboardEvent('keydown', {key: 'Tab', shiftKey, bubbles: true, cancelable: true});
    window.document.activeElement.dispatchEvent(event);
    return event.defaultPrevented;
  }
  assert(tab());
  assert.equal(window.document.activeElement, dialog.querySelector('input'));
  assert(tab(true));
  assert.equal(window.document.activeElement, checked);
  dialog.insertAdjacentHTML('beforeend', '<form><input type="radio" name="choice" checked id="independent"></form>');
  const independent = dialog.querySelector('#independent');
  independent.getClientRects = () => [{}];
  checked.focus();
  assert.equal(tab(), false, 'Same name under another form is a distinct group');
  independent.focus();
  assert(tab());
  dialog.insertAdjacentHTML('beforeend', '<input type="radio" id="unnamed">');
  const unnamed = dialog.querySelector('#unnamed');
  unnamed.getClientRects = () => [{}];
  unnamed.focus();
  assert(tab());
  controller.destroy();
  window.close();
});

test('unchecked radio groups and disabled checked members retain usable edges', () => {
  for (const disabledChecked of [false, true]) {
    const {window, dialog, trigger} = fixture();
    dialog.insertAdjacentHTML('beforeend', `<input type="radio" name="choice" id="first"><input type="radio" name="choice" id="last">${disabledChecked ? '<input type="radio" name="choice" checked disabled>' : ''}`);
    for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
    const controller = createDialog(dialog);
    controller.open(trigger);
    const initial = dialog.querySelector('input');
    initial.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true}));
    const last = dialog.querySelector('#last');
    assert.equal(window.document.activeElement, last);
    const forward = new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true});
    last.dispatchEvent(forward);
    assert(forward.defaultPrevented);
    assert.equal(window.document.activeElement, initial);
    controller.destroy();
    window.close();
  }
});

test('focus return uses the fallback when a fieldset disables the invoker', () => {
  const {window, dialog, trigger, fallback} = fixture();
  const fieldset = window.document.createElement('fieldset');
  trigger.before(fieldset);
  fieldset.append(trigger);
  const controller = createDialog(dialog, {fallbackFocus: fallback});
  controller.open(trigger);
  fieldset.disabled = true;
  assert.equal(trigger.disabled, false);
  assert(trigger.matches(':disabled'));
  controller.close();
  assert.equal(window.document.activeElement, fallback);
  controller.destroy();
  window.close();
});

test('a composite widget can consume Tab without dialog interference', () => {
  const {window, dialog, trigger} = fixture();
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
  const controller = createDialog(dialog);
  controller.open(trigger);
  const last = dialog.querySelector('button');
  last.addEventListener('keydown', event => {if (event.key === 'Tab') event.preventDefault();});
  last.focus();
  last.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true}));
  assert.equal(window.document.activeElement, last);
  controller.destroy();
  window.close();
});

test('disabled fieldset first-legend exception still restores its invoker', () => {
  const {window, dialog, trigger, fallback} = fixture();
  const fieldset = window.document.createElement('fieldset');
  const legend = window.document.createElement('legend');
  trigger.before(fieldset);
  fieldset.append(legend);
  legend.append(trigger);
  const controller = createDialog(dialog, {fallbackFocus: fallback});
  controller.open(trigger);
  fieldset.disabled = true;
  assert.equal(trigger.matches(':disabled'), false);
  controller.close();
  assert.equal(window.document.activeElement, trigger);
  controller.destroy();
  window.close();
});

test('computed hidden and collapsed controls do not become dialog edges', () => {
  const {window, dialog, trigger} = fixture();
  dialog.insertAdjacentHTML('beforeend', '<button style="visibility:hidden">Hidden</button><button style="visibility:collapse">Collapsed</button>');
  for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
  const controller = createDialog(dialog);
  controller.open(trigger);
  const last = dialog.querySelector('button');
  last.focus();
  const event = new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true});
  last.dispatchEvent(event);
  assert(event.defaultPrevented);
  assert.equal(window.document.activeElement, dialog.querySelector('input'));
  controller.destroy();
  window.close();
});

test('empty, true and plaintext-only editable roots are dialog tab stops', () => {
  for (const value of ['', 'true', 'plaintext-only']) {
    const {window, dialog, trigger} = fixture();
    dialog.insertAdjacentHTML('beforeend', `<div contenteditable="${value}">Editor</div>`);
    const editor = dialog.querySelector('[contenteditable]');
    for (const node of dialog.querySelectorAll('*')) node.getClientRects = () => [{}];
    const controller = createDialog(dialog);
    controller.open(trigger);
    // jsdom does not implement native editing-host focusability.
    Object.defineProperty(window.document, 'activeElement', {configurable: true, get: () => editor});
    const event = new window.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true});
    editor.dispatchEvent(event);
    assert(event.defaultPrevented, `Editable state ${JSON.stringify(value)} wraps at the edge`);
    delete window.document.activeElement;
    controller.destroy();
    window.close();
  }
});

test('a connected invoker whose focus fails falls back to a usable destination', () => {
  const {window, dialog, trigger, fallback} = fixture();
  const controller = createDialog(dialog, {fallbackFocus: fallback});
  controller.open(trigger);
  // jsdom does not implement inert or rendering-dependent focus eligibility.
  trigger.focus = () => {};
  controller.close();
  assert.equal(window.document.activeElement, fallback);
  controller.destroy();
  window.close();
});
