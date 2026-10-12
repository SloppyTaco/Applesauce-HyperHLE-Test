import UIKit
import Foundation
import CoreFoundation
import Darwin

@main
@MainActor
final class ResumeAppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     configurationForConnecting session: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let configuration = UISceneConfiguration(name: "Resume", sessionRole: session.role)
        configuration.delegateClass = ResumeScene.self
        return configuration
    }
}

@objc(ResumeScene)
@MainActor
final class ResumeScene: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    private var harness: ResumeHarness?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
               options connectionOptions: UIScene.ConnectionOptions) {
        guard let scene = scene as? UIWindowScene else { return }
        let harness = ResumeHarness(scene: scene)
        self.harness = harness
        window = harness.gameWindow
        harness.start()
    }
}

@MainActor
final class ResumePassThroughWindow: UIWindow {
    weak var interactiveView: UIView?
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        guard let hit = super.hitTest(point, with: event), let interactiveView,
              hit === interactiveView || hit.isDescendant(of: interactiveView) else { return nil }
        return hit
    }
}

@MainActor
final class ResumeRootController: UIViewController {
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscapeLeft }
    override var shouldAutorotate: Bool { true }
}

@MainActor
final class ResumeHarness: NSObject {
    let gameWindow: UIWindow
    private let controlsWindow: ResumePassThroughWindow
    private let status = UILabel()
    private let foreground = UILabel()
    private let heartbeat = UILabel()
    private let gameButton = UIButton(type: .system)
    private let exitButton = UIButton(type: .system)
    private var heartbeatTimer: Timer?
    private var running = false
    private var entries = 0
    private var probes = 0
    private var beats = 0
    private var taps = 0
    private var inactiveSignals = 0
    private var activeCompletions = 0
    private let baseline = ProcessInfo.processInfo.environment["RESUME_BASELINE"] == "1"
    private let logURL: URL

    init(scene: UIWindowScene) {
        gameWindow = UIWindow(windowScene: scene)
        controlsWindow = ResumePassThroughWindow(windowScene: scene)
        logURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("native-resume-v23.log")
        super.init()
        try? Data().write(to: logURL)
        let root = ResumeRootController()
        root.view.backgroundColor = .systemIndigo
        gameWindow.rootViewController = root
        status.text = "Waiting for core"
        status.accessibilityIdentifier = "resume-status"
        foreground.text = "Foreground 0"
        foreground.accessibilityIdentifier = "resume-foreground"
        heartbeat.text = "Heartbeat 0"
        for label in [status, foreground, heartbeat] {
            label.textColor = .white
            label.textAlignment = .center
        }
        gameButton.setTitle("Game touch", for: .normal)
        gameButton.accessibilityIdentifier = "resume-game-touch"
        gameButton.backgroundColor = .white
        gameButton.addTarget(self, action: #selector(gameTouch(_:)), for: .touchUpInside)
        let stack = UIStackView(arrangedSubviews: [status, foreground, heartbeat, gameButton])
        stack.axis = .vertical
        stack.spacing = 15
        stack.translatesAutoresizingMaskIntoConstraints = false
        root.view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: root.view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: root.view.centerYAnchor),
            stack.widthAnchor.constraint(equalToConstant: 320),
            gameButton.heightAnchor.constraint(equalToConstant: 64)
        ])
        let overlay = ResumeRootController()
        overlay.view.backgroundColor = .clear
        controlsWindow.rootViewController = overlay
        controlsWindow.windowLevel = .alert + 1
        controlsWindow.interactiveView = exitButton
        exitButton.setTitle("Exit core", for: .normal)
        exitButton.accessibilityIdentifier = "resume-exit"
        exitButton.backgroundColor = .systemRed
        exitButton.setTitleColor(.white, for: .normal)
        exitButton.translatesAutoresizingMaskIntoConstraints = false
        exitButton.addTarget(self, action: #selector(exitCore(_:)), for: .touchUpInside)
        overlay.view.addSubview(exitButton)
        NSLayoutConstraint.activate([
            exitButton.topAnchor.constraint(equalTo: overlay.view.safeAreaLayoutGuide.topAnchor, constant: 10),
            exitButton.trailingAnchor.constraint(equalTo: overlay.view.safeAreaLayoutGuide.trailingAnchor, constant: -10),
            exitButton.widthAnchor.constraint(equalToConstant: 100),
            exitButton.heightAnchor.constraint(equalToConstant: 44)
        ])
        gameWindow.makeKeyAndVisible()
        controlsWindow.isHidden = false
        NotificationCenter.default.addObserver(self, selector: #selector(resigned(_:)),
            name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(activated(_:)),
            name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    private func log(_ message: String) {
        let line = "[NATIVE RESUME v23] " + message + "\n"
        print(line, terminator: "")
        if let handle = try? FileHandle(forWritingTo: logURL) {
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: Data(line.utf8))
            try? handle.close()
        }
    }

    func start() {
        heartbeatTimer = Timer.scheduledTimer(timeInterval: 0.05, target: self,
            selector: #selector(tick(_:)), userInfo: nil, repeats: true)
        // Use the old final launch context for the baseline. The fixed entry
        // uses the exact production helper, without replacing SDL's pump.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if self.baseline {
                self.runCore()
            } else {
                TouchHLEMainRunLoopLaunch.schedule { self.runCore() }
            }
        }
    }

    @objc private func tick(_ timer: Timer) {
        guard UIApplication.shared.applicationState == .active else { return }
        beats += 1
        heartbeat.text = "Heartbeat \(beats)"
    }

    @objc private func resigned(_ notification: NSNotification) {
        guard running else { return }
        inactiveSignals += 1
        log("Inactive signal \(inactiveSignals)")
    }

    @objc private func activated(_ notification: NSNotification) {
        guard running else { return }
        log("Native active signal; queued UIKit-style completion")
        DispatchQueue.main.async {
            guard self.running else { return }
            precondition(Thread.isMainThread)
            self.activeCompletions += 1
            self.foreground.text = "Foreground \(self.activeCompletions)"
            self.log("Foreground completion \(self.activeCompletions) serviced during core")
        }
    }

    @objc private func gameTouch(_ button: UIButton) {
        guard running else { return }
        taps += 1
        status.text = "Tap \(taps)"
        log("Actual game tap \(taps) delivered")
    }

    @objc private func exitCore(_ button: UIButton) {
        guard running else { return }
        guard !baseline, entries == 1, probes == 1, taps == 4,
              inactiveSignals >= 3, activeCompletions >= 3 else {
            status.text = "Resume checks failed"
            log("FAIL exit: entries=\(entries) probes=\(probes) taps=\(taps) inactive=\(inactiveSignals) active=\(activeCompletions)")
            running = false
            return
        }
        running = false
        status.text = "All resume taps passed"
        log("ALL PASS 5 actual taps, 3 interruptions, one main-thread core entry")
    }

    private func runCore() {
        precondition(Thread.isMainThread)
        entries += 1
        running = true
        let start = ProcessInfo.processInfo.systemUptime
        let deadline = start + (baseline ? 12 : 150)
        status.text = "Core running"
        log("START \(baseline ? "baseline main dispatch" : "fixed native timer")")
        DispatchQueue.main.async {
            precondition(Thread.isMainThread)
            guard self.running else {
                self.log("Queue probe delivered only after core returned")
                return
            }
            self.probes += 1
            self.status.text = "Core ready"
            self.log("PASS main dispatch completion serviced inside core")
        }
        var reportedBaseline = false
        while running && ProcessInfo.processInfo.systemUptime < deadline {
            // Exact native SDL UIKit default/tracking run-loop turns.
            while CFRunLoopRunInMode(.defaultMode, 0.000002, true) == .handledSource {}
            let tracking = CFRunLoopMode(rawValue: "UITrackingRunLoopMode" as CFString)
            while CFRunLoopRunInMode(tracking, 0.000002, true) == .handledSource {}
            usleep(1000)
            if baseline && !reportedBaseline && ProcessInfo.processInfo.systemUptime - start > 2 {
                reportedBaseline = true
                if probes == 0 && beats >= 10 {
                    status.text = "Baseline queue blocked"
                    log("BASELINE queue blocked while heartbeat advances")
                } else {
                    status.text = "Baseline not reproduced"
                    log("FAIL baseline not reproduced: probes=\(probes) beats=\(beats)")
                }
            }
        }
        running = false
        if !baseline && taps != 4 { log("FAIL core timed out before all input checks") }
        log("RETURN core; entry count \(entries); main thread \(Thread.isMainThread)")
    }
}
