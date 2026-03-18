NAME    = ora
VERSION = 1.0.0
ARCH    = all
PKG     = $(NAME)_$(VERSION)_$(ARCH)

.PHONY: deb clean

deb: $(PKG).deb

$(PKG).deb: _build
	fakeroot dpkg-deb --build $(PKG)
	@echo ""
	@echo "✓ Package built: $(PKG).deb"
	@echo "  Install with: sudo dpkg -i $(PKG).deb"

_build:
	@which fakeroot  > /dev/null || (echo "Missing: fakeroot  → sudo apt install fakeroot"  && exit 1)
	@which dpkg-deb  > /dev/null || (echo "Missing: dpkg-deb  → sudo apt install dpkg-dev"  && exit 1)

	mkdir -p $(PKG)/DEBIAN
	mkdir -p $(PKG)/usr/bin
	mkdir -p $(PKG)/usr/lib/$(NAME)
	mkdir -p $(PKG)/usr/share/applications
	mkdir -p $(PKG)/usr/share/doc/$(NAME)

	# App
	install -m 644 ora.py $(PKG)/usr/lib/$(NAME)/ora.py

	# Launcher wrapper
	printf '#!/bin/sh\nexec python3 /usr/lib/$(NAME)/ora.py "$$@"\n' \
		> $(PKG)/usr/bin/$(NAME)
	chmod 755 $(PKG)/usr/bin/$(NAME)

	# Desktop entry
	printf '%s\n' \
		'[Desktop Entry]' \
		'Name=Ora' \
		'Comment=Neural Text-to-Speech' \
		'Exec=ora' \
		'Icon=audio-input-microphone' \
		'Terminal=false' \
		'Type=Application' \
		'Categories=AudioVideo;Audio;' \
		> $(PKG)/usr/share/applications/$(NAME).desktop

	# Readme
	install -m 644 README.md $(PKG)/usr/share/doc/$(NAME)/README.md

	# DEBIAN/control
	printf '%s\n' \
		'Package: $(NAME)' \
		'Version: $(VERSION)' \
		'Architecture: $(ARCH)' \
		'Maintainer: $(NAME) <noreply@example.com>' \
		'Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, alsa-utils' \
		'Section: sound' \
		'Priority: optional' \
		'Description: Neural text-to-speech for Linux' \
		' Ora is a GTK3 TTS application powered by Piper. Supports 30+ languages,' \
		' auto-downloads voice models, works fully offline after setup.' \
		> $(PKG)/DEBIAN/control

	# DEBIAN/postinst — install pip dependencies
	printf '%s\n' \
		'#!/bin/sh' \
		'set -e' \
		'pip3 install piper-tts pathvalidate --break-system-packages --quiet 2>/dev/null || true' \
		> $(PKG)/DEBIAN/postinst
	chmod 755 $(PKG)/DEBIAN/postinst

clean:
	rm -rf $(PKG) $(PKG).deb
