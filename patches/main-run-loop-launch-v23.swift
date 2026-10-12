// Keep the emulator on the main thread, without holding a main-dispatch block.
// SDL's nested run-loop turns can then service queued UIKit completion work.
@MainActor
final class TouchHLEMainRunLoopLaunch: NSObject {
    private var completion: (@MainActor () -> Void)?

    private init(completion: @escaping @MainActor () -> Void) {
        self.completion = completion
        super.init()
    }

    static func schedule(_ completion: @escaping @MainActor () -> Void) {
        precondition(Thread.isMainThread)
        let entry = TouchHLEMainRunLoopLaunch(completion: completion)
        let timer = Timer(
            timeInterval: 0.01,
            target: entry,
            selector: #selector(TouchHLEMainRunLoopLaunch.fire(_:)),
            userInfo: nil,
            repeats: true
        )
        // A timer fires after the scheduling dispatch block has returned.
        // Default mode also avoids starting during an active tracking gesture.
        RunLoop.main.add(timer, forMode: .default)
    }

    @objc private func fire(_ timer: Timer) {
        precondition(Thread.isMainThread)
        guard UIApplication.shared.applicationState == .active else { return }
        guard let completion else {
            timer.invalidate()
            return
        }
        self.completion = nil
        timer.invalidate()
        NSLog("[MAIN RUN LOOP v23] Starting emulator from native run-loop timer on main thread")
        withExtendedLifetime(self) {
            completion()
        }
    }
}
