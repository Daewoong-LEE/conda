import AppKit
import SwiftUI

// MARK: - AppDelegate

final class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusItem:  NSStatusItem!
    private var popover:     NSPopover!
    private var timer:       Timer?

    let monitor = TokenMonitor()

    // MARK: Lifecycle

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupPopover()
        startTimer()
        monitor.onUpdate = { [weak self] in self?.syncStatusBar() }
        monitor.refresh()
    }

    // MARK: Setup

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        guard let button = statusItem.button else { return }
        button.title          = "☁ …"
        button.action         = #selector(handleStatusBarClick(_:))
        button.target         = self
        button.sendAction(on: [.leftMouseUp, .rightMouseUp])
    }

    private func setupPopover() {
        let root = ContentView()
            .environmentObject(monitor)

        let hostVC = NSHostingController(rootView: root)
        hostVC.view.layer?.cornerRadius = 16

        popover                    = NSPopover()
        popover.contentSize        = NSSize(width: 340, height: 410)
        popover.behavior           = .transient
        popover.animates           = true
        popover.contentViewController = hostVC

        // Match the blue background so no white flash on appear
        popover.appearance = NSAppearance(named: .aqua)
    }

    private func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            self?.monitor.refresh()
        }
        RunLoop.main.add(timer!, forMode: .common)
    }

    // MARK: Status-bar interaction

    @objc private func handleStatusBarClick(_ sender: NSStatusBarButton) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            monitor.refresh()
            popover.show(relativeTo: sender.bounds, of: sender, preferredEdge: .minY)
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    // MARK: Status-bar label sync

    func syncStatusBar() {
        guard let button = statusItem?.button else { return }
        let pct  = Int(monitor.usagePercentage * 100)
        let mins = monitor.minutesRemaining

        let label: String
        if mins > 0 {
            label = "☁ \(pct)% · \(mins)m"
        } else {
            label = "☁ \(pct)%"
        }

        // Colour the percentage green when low, orange/red when high
        let pctColor: NSColor = {
            switch pct {
            case ..<60:  return NSColor(red: 0.19, green: 0.82, blue: 0.35, alpha: 1)
            case ..<85:  return .orange
            default:     return .systemRed
            }
        }()

        let attr = NSMutableAttributedString(string: label)
        let fullRange = NSRange(label.startIndex..., in: label)
        attr.addAttribute(.foregroundColor, value: NSColor.labelColor, range: fullRange)

        // Colour just the "N%" part
        if let pctRange = label.range(of: "\(pct)%") {
            let nsRange = NSRange(pctRange, in: label)
            attr.addAttribute(.foregroundColor, value: pctColor, range: nsRange)
        }

        button.attributedTitle = attr
    }
}
